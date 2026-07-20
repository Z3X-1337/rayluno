"""Injectable HTTPS transport used by the update client."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from http.client import HTTPException
from typing import BinaryIO, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..identity import PRODUCT_NAME
from .errors import DownloadSizeError, UpdateTransportError
from .models import validate_https_url


class UpdateResponse(Protocol):
    final_url: str

    def read(self, size: int = -1) -> bytes: ...


class UpdateTransport(Protocol):
    def open(self, url: str, *, timeout: float) -> AbstractContextManager[UpdateResponse]: ...


@dataclass(slots=True)
class _NetworkResponse:
    stream: BinaryIO
    final_url: str

    def read(self, size: int = -1) -> bytes:
        try:
            return self.stream.read(size)
        except (HTTPException, URLError, TimeoutError, OSError) as exc:
            raise UpdateTransportError("update response failed while streaming") from exc


class _HttpsOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        response: BinaryIO,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> Request | None:
        validate_https_url(new_url)
        return super().redirect_request(request, response, code, message, headers, new_url)


class UrllibUpdateTransport:
    """Small stdlib transport with normal platform TLS certificate validation."""

    @contextmanager
    def open(self, url: str, *, timeout: float) -> Iterator[UpdateResponse]:
        validate_https_url(url)
        request = Request(
            url,
            headers={
                "Accept": "application/json, application/octet-stream",
                "User-Agent": f"{PRODUCT_NAME}-Updater/1",
            },
            method="GET",
        )
        try:
            response = build_opener(_HttpsOnlyRedirectHandler()).open(request, timeout=timeout)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise UpdateTransportError("update request failed") from exc
        try:
            final_url = response.geturl()
            validate_https_url(final_url)
            yield _NetworkResponse(response, final_url)
        finally:
            response.close()


def read_limited_response(
    transport: UpdateTransport,
    url: str,
    *,
    max_bytes: int,
    timeout: float,
    chunk_size: int = 64 * 1024,
) -> bytes:
    """Read a small response while enforcing HTTPS before and after redirects."""

    validate_https_url(url)
    if max_bytes <= 0 or chunk_size <= 0:
        raise ValueError("response limits must be positive")
    chunks: list[bytes] = []
    total = 0
    with transport.open(url, timeout=timeout) as response:
        validate_https_url(response.final_url)
        while True:
            chunk = response.read(min(chunk_size, max_bytes - total + 1))
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise UpdateTransportError("update transport returned non-byte data")
            total += len(chunk)
            if total > max_bytes:
                raise DownloadSizeError("response exceeded its configured size limit")
            chunks.append(chunk)
    return b"".join(chunks)
