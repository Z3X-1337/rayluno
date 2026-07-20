"""Safe online activation boundary for exchanging purchase keys for offline tokens.

The desktop application never embeds a payment-provider API key or the Ed25519
license signing key.  It sends a purchase key once to the configured HTTPS
activation service, verifies the returned signed token through the existing
entitlement boundary, and keeps only an opaque refresh token protected by
Windows DPAPI.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from .identity import (
    COMPATIBILITY_DATA_DIRECTORY,
    PRODUCT_DISPLAY_NAME,
    PRODUCT_NAME,
    environment_value,
)

ACTIVATION_PROTOCOL_VERSION: Final = 1
PRODUCTION_ACTIVATION_ENDPOINT: Final = (
    "https://future-assistant-local.zaid-hj2003.chatgpt.site/api/license/activate"
)
MAX_RESPONSE_BYTES: Final = 131_072
MAX_STATE_BYTES: Final = 16_384
_PURCHASE_KEY_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{11,255}$")
_REFRESH_TOKEN_PATTERN: Final = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_INSTANCE_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_DPAPI_ENTROPY: Final = b"future-assistant-activation-state-v1"


class ActivationError(RuntimeError):
    """Base class for failures safe to collapse at the UI boundary."""


class ActivationConfigurationError(ActivationError):
    """The activation service is not configured safely."""


class ActivationTransportError(ActivationError):
    """The activation service could not be reached or returned invalid data."""


class ActivationRejectedError(ActivationError):
    """The server rejected an activation without exposing provider details."""

    def __init__(self, code: str = "activation_rejected") -> None:
        self.code = code
        super().__init__(code)


class ActivationStorageError(ActivationError):
    """Local protected activation state could not be read or written."""


def _validate_endpoint(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 2_048:
        raise ActivationConfigurationError("activation endpoint is missing or too long")
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ActivationConfigurationError("activation endpoint must be a plain HTTPS URL")
    if parsed.port not in (None, 443):
        raise ActivationConfigurationError("activation endpoint must use the HTTPS port")
    return value


@dataclass(frozen=True, slots=True)
class ActivationConfig:
    """Non-secret desktop activation settings."""

    endpoint: str | None = None
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        if self.endpoint is not None:
            object.__setattr__(self, "endpoint", _validate_endpoint(self.endpoint))
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not 1 <= float(self.timeout_seconds) <= 30
        ):
            raise ActivationConfigurationError(
                "activation timeout must be between 1 and 30 seconds"
            )

    @property
    def configured(self) -> bool:
        return self.endpoint is not None

    @classmethod
    def from_env(cls) -> ActivationConfig:
        """Return the pinned production endpoint, with a source-only dev override.

        A purchase key is a credential.  A generic HTTPS environment override would
        allow an injected launcher environment to send it to an attacker-controlled
        TLS origin.  Frozen customer builds therefore always use the exact production
        endpoint.  Source checkouts may opt into a staging endpoint explicitly.
        """

        endpoint = PRODUCTION_ACTIVATION_ENDPOINT
        override = environment_value("ACTIVATION_URL").strip()
        allow_development_override = not bool(
            getattr(sys, "frozen", False)
        ) and environment_value("ALLOW_ACTIVATION_OVERRIDE").strip().casefold() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if override and allow_development_override:
            endpoint = override
        return cls(endpoint=endpoint)


class ActivationTransport(Protocol):
    def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout_seconds: float,
    ) -> Mapping[str, object]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


def _strict_json_object(raw: bytes) -> dict[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ActivationTransportError("activation response contains duplicate fields")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicates)
    except ActivationTransportError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise ActivationTransportError("activation response is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ActivationTransportError("activation response must be a JSON object")
    return value


class UrlLibActivationTransport:
    """Small HTTPS JSON transport that refuses redirects and oversized replies."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect())

    def post_json(
        self,
        url: str,
        payload: Mapping[str, object],
        *,
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        endpoint = _validate_endpoint(url)
        try:
            body = json.dumps(
                dict(payload),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise ActivationTransportError("activation request is invalid") from exc
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": f"{PRODUCT_NAME}/activation-v1",
            },
        )
        try:
            response = self._opener.open(request, timeout=timeout_seconds)
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                raw = exc.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) <= MAX_RESPONSE_BYTES:
                    return _strict_json_object(raw)
            raise ActivationTransportError("activation service rejected the request") from exc
        except (OSError, urllib.error.URLError) as exc:
            raise ActivationTransportError("activation service is unavailable") from exc
        with response:
            content_type = response.headers.get_content_type()
            if content_type != "application/json":
                raise ActivationTransportError("activation response has an invalid content type")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ActivationTransportError("activation response is too large")
        return _strict_json_object(raw)


@dataclass(frozen=True, slots=True)
class ActivationGrant:
    license_token: str
    refresh_token: str
    instance_id: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.license_token, str)
            or not 20 <= len(self.license_token.encode("utf-8")) <= 16_384
        ):
            raise ActivationTransportError("activation returned an invalid license token")
        if not isinstance(self.refresh_token, str) or not _REFRESH_TOKEN_PATTERN.fullmatch(
            self.refresh_token
        ):
            raise ActivationTransportError("activation returned an invalid refresh token")
        if not isinstance(self.instance_id, str) or not _INSTANCE_ID_PATTERN.fullmatch(
            self.instance_id
        ):
            raise ActivationTransportError("activation returned an invalid instance identifier")


class ActivationClient:
    """Exchange a purchase key or refresh token through the trusted service."""

    def __init__(
        self,
        config: ActivationConfig,
        *,
        transport: ActivationTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport or UrlLibActivationTransport()

    def activate(
        self,
        purchase_key: str,
        installation_id: str,
        *,
        app_version: str,
    ) -> ActivationGrant:
        if not isinstance(purchase_key, str) or not _PURCHASE_KEY_PATTERN.fullmatch(
            purchase_key.strip()
        ):
            raise ActivationRejectedError("invalid_purchase_key")
        return self._request(
            {
                "protocol": ACTIVATION_PROTOCOL_VERSION,
                "action": "activate",
                "purchase_key": purchase_key.strip(),
                "installation_id": _installation_id(installation_id),
                "app_version": app_version,
            }
        )

    def refresh(
        self,
        refresh_token: str,
        installation_id: str,
        *,
        app_version: str,
    ) -> ActivationGrant:
        if not isinstance(refresh_token, str) or not _REFRESH_TOKEN_PATTERN.fullmatch(
            refresh_token
        ):
            raise ActivationRejectedError("invalid_refresh_token")
        return self._request(
            {
                "protocol": ACTIVATION_PROTOCOL_VERSION,
                "action": "refresh",
                "refresh_token": refresh_token,
                "installation_id": _installation_id(installation_id),
                "app_version": app_version,
            }
        )

    def deactivate(
        self,
        refresh_token: str,
        installation_id: str,
        *,
        app_version: str,
    ) -> None:
        """Release the provider device slot before local activation is removed."""

        if not isinstance(refresh_token, str) or not _REFRESH_TOKEN_PATTERN.fullmatch(
            refresh_token
        ):
            raise ActivationRejectedError("invalid_refresh_token")
        endpoint = self.config.endpoint
        if endpoint is None:
            raise ActivationConfigurationError("activation service is not configured")
        response = self._transport.post_json(
            endpoint,
            {
                "protocol": ACTIVATION_PROTOCOL_VERSION,
                "action": "deactivate",
                "refresh_token": refresh_token,
                "installation_id": _installation_id(installation_id),
                "app_version": app_version,
            },
            timeout_seconds=float(self.config.timeout_seconds),
        )
        if response.get("ok") is False:
            if set(response) != {"ok", "code"} or not isinstance(response.get("code"), str):
                raise ActivationTransportError("activation error response is invalid")
            code = str(response["code"])
            if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", code):
                raise ActivationTransportError("activation error code is invalid")
            raise ActivationRejectedError(code)
        if response != {"ok": True, "deactivated": True}:
            raise ActivationTransportError("deactivation response is invalid")

    def _request(self, payload: Mapping[str, object]) -> ActivationGrant:
        endpoint = self.config.endpoint
        if endpoint is None:
            raise ActivationConfigurationError("activation service is not configured")
        response = self._transport.post_json(
            endpoint,
            payload,
            timeout_seconds=float(self.config.timeout_seconds),
        )
        ok = response.get("ok")
        if ok is False:
            if set(response) != {"ok", "code"} or not isinstance(response.get("code"), str):
                raise ActivationTransportError("activation error response is invalid")
            code = str(response["code"])
            if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", code):
                raise ActivationTransportError("activation error code is invalid")
            raise ActivationRejectedError(code)
        expected = {"ok", "license_token", "refresh_token", "instance_id"}
        if ok is not True or set(response) != expected:
            raise ActivationTransportError("activation response is missing required fields")
        return ActivationGrant(
            license_token=response["license_token"],  # type: ignore[arg-type]
            refresh_token=response["refresh_token"],  # type: ignore[arg-type]
            instance_id=response["instance_id"],  # type: ignore[arg-type]
        )


def _installation_id(value: str) -> str:
    if not isinstance(value, str):
        raise ActivationStorageError("installation identifier is invalid")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ActivationStorageError("installation identifier is invalid") from exc
    if parsed.version != 4 or str(parsed) != value.lower():
        raise ActivationStorageError("installation identifier is invalid")
    return str(parsed)


def default_activation_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data).expanduser()
    elif os.name == "nt":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / COMPATIBILITY_DATA_DIRECTORY / "activation"


def _atomic_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = -1
    temporary: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary = Path(raw_path)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        with suppress(OSError):
            temporary.chmod(0o600)
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise ActivationStorageError("could not save protected activation state") from exc
    finally:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        if temporary is not None:
            with suppress(FileNotFoundError):
                temporary.unlink()


class InstallationIdentityStore:
    """Persist a random installation identifier without fingerprinting hardware."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = Path(directory) if directory else default_activation_directory()
        self.path = self.directory / "installation.json"
        self._lock = threading.RLock()

    def load_or_create(self) -> str:
        with self._lock:
            try:
                raw = self.path.read_bytes()
            except FileNotFoundError:
                installation_id = str(uuid.uuid4())
                document = {"version": 1, "installation_id": installation_id}
                _atomic_write(
                    self.path,
                    (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode(
                        "utf-8"
                    ),
                )
                return installation_id
            except OSError as exc:
                raise ActivationStorageError("could not read installation identity") from exc
            if not raw or len(raw) > 1_024:
                raise ActivationStorageError("installation identity is invalid")
            document = _strict_json_object(raw)
            if set(document) != {"version", "installation_id"} or document["version"] != 1:
                raise ActivationStorageError("installation identity is invalid")
            return _installation_id(document["installation_id"])  # type: ignore[arg-type]


class DataProtector(Protocol):
    def protect(self, plaintext: bytes) -> bytes: ...

    def unprotect(self, ciphertext: bytes) -> bytes: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _input_blob(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value)
    pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    return _DataBlob(len(value), pointer), buffer


class WindowsDataProtector:
    """Protect small secrets with the current Windows user's DPAPI profile."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise ActivationStorageError("protected activation storage requires Windows")
        self._crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def protect(self, plaintext: bytes) -> bytes:
        if not isinstance(plaintext, bytes) or not plaintext or len(plaintext) > MAX_STATE_BYTES:
            raise ActivationStorageError("activation state is empty or too large")
        return self._call("CryptProtectData", plaintext)

    def unprotect(self, ciphertext: bytes) -> bytes:
        if (
            not isinstance(ciphertext, bytes)
            or not ciphertext
            or len(ciphertext) > MAX_STATE_BYTES * 4
        ):
            raise ActivationStorageError("protected activation state is invalid")
        return self._call("CryptUnprotectData", ciphertext)

    def _call(self, function_name: str, value: bytes) -> bytes:
        input_blob, input_buffer = _input_blob(value)
        entropy_blob, entropy_buffer = _input_blob(_DPAPI_ENTROPY)
        output_blob = _DataBlob()
        function = getattr(self._crypt32, function_name)
        if function_name == "CryptProtectData":
            success = function(
                ctypes.byref(input_blob),
                f"{PRODUCT_DISPLAY_NAME} activation",
                ctypes.byref(entropy_blob),
                None,
                None,
                0x1,
                ctypes.byref(output_blob),
            )
        else:
            success = function(
                ctypes.byref(input_blob),
                None,
                ctypes.byref(entropy_blob),
                None,
                None,
                0x1,
                ctypes.byref(output_blob),
            )
        del input_buffer, entropy_buffer
        if not success:
            raise ActivationStorageError("Windows could not protect activation state")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            self._kernel32.LocalFree(output_blob.pbData)


@dataclass(frozen=True, slots=True)
class StoredActivation:
    installation_id: str
    refresh_token: str
    instance_id: str

    def __post_init__(self) -> None:
        _installation_id(self.installation_id)
        if not _REFRESH_TOKEN_PATTERN.fullmatch(self.refresh_token):
            raise ActivationStorageError("stored refresh token is invalid")
        if not _INSTANCE_ID_PATTERN.fullmatch(self.instance_id):
            raise ActivationStorageError("stored instance identifier is invalid")


class ActivationStateStore:
    """Atomically store opaque refresh credentials protected by Windows DPAPI."""

    def __init__(
        self,
        directory: Path | None = None,
        *,
        protector: DataProtector | None = None,
    ) -> None:
        self.directory = Path(directory) if directory else default_activation_directory()
        self.path = self.directory / "state.bin"
        self._protector = protector or WindowsDataProtector()
        self._lock = threading.RLock()

    def save(self, state: StoredActivation) -> None:
        document = {
            "version": 1,
            "installation_id": state.installation_id,
            "refresh_token": state.refresh_token,
            "instance_id": state.instance_id,
        }
        plaintext = json.dumps(
            document,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        protected = self._protector.protect(plaintext)
        encoded = base64.urlsafe_b64encode(protected) + b"\n"
        with self._lock:
            _atomic_write(self.path, encoded)

    def load(self) -> StoredActivation | None:
        with self._lock:
            try:
                encoded = self.path.read_bytes()
            except FileNotFoundError:
                return None
            except OSError as exc:
                raise ActivationStorageError("could not read protected activation state") from exc
        if not encoded or len(encoded) > MAX_STATE_BYTES * 6:
            raise ActivationStorageError("protected activation state is invalid")
        try:
            protected = base64.b64decode(encoded.strip(), altchars=b"-_", validate=True)
        except (ValueError, TypeError) as exc:
            raise ActivationStorageError("protected activation state is invalid") from exc
        plaintext = self._protector.unprotect(protected)
        if not plaintext or len(plaintext) > MAX_STATE_BYTES:
            raise ActivationStorageError("protected activation state is invalid")
        document = _strict_json_object(plaintext)
        expected = {"version", "installation_id", "refresh_token", "instance_id"}
        if set(document) != expected or document["version"] != 1:
            raise ActivationStorageError("protected activation state is invalid")
        try:
            return StoredActivation(
                installation_id=document["installation_id"],  # type: ignore[arg-type]
                refresh_token=document["refresh_token"],  # type: ignore[arg-type]
                instance_id=document["instance_id"],  # type: ignore[arg-type]
            )
        except (TypeError, ValueError, ActivationError) as exc:
            raise ActivationStorageError("protected activation state is invalid") from exc

    def remove(self) -> bool:
        with self._lock:
            try:
                self.path.unlink()
            except FileNotFoundError:
                return False
            except OSError as exc:
                raise ActivationStorageError("could not remove protected activation state") from exc
            return True
