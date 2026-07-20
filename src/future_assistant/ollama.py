"""Tiny standard-library Ollama client with an injectable transport."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

_PLAN_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["search", "youtube", "open_site", "open_app", "time", "volume", "reply"],
        },
        "query": {"type": "string"},
        "site": {"type": "string"},
        "app": {"type": "string"},
        "operation": {"type": "string", "enum": ["up", "down", "toggle_mute"]},
        "text": {"type": "string"},
    },
    "required": ["intent"],
    "additionalProperties": False,
}


class OllamaError(RuntimeError):
    pass


class JsonTransport(Protocol):
    def post_json(
        self, url: str, payload: Mapping[str, Any], timeout: float
    ) -> Mapping[str, Any]: ...


class UrllibJsonTransport:
    def post_json(self, url: str, payload: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                body = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise OllamaError(f"تعذر الاتصال بمحرك الذكاء المحلي: {exc}") from exc
        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise OllamaError("أعاد Ollama استجابة غير صالحة.") from exc
        if not isinstance(result, dict):
            raise OllamaError("أعاد Ollama نوع استجابة غير متوقع.")
        return result


@dataclass(frozen=True, slots=True)
class OllamaClient:
    endpoint: str
    model: str
    timeout: float = 20.0
    transport: JsonTransport = UrllibJsonTransport()

    def __post_init__(self) -> None:
        parts = urlsplit(self.endpoint)
        if parts.scheme not in {"http", "https"}:
            raise ValueError("Ollama endpoint must use HTTP or HTTPS.")
        if parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Ollama endpoint must be local to prevent SSRF.")
        try:
            _ = parts.port
        except ValueError as exc:
            raise ValueError("Ollama endpoint contains an invalid port.") from exc
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("Ollama endpoint cannot contain credentials, query, or fragment.")
        if not self.model.strip():
            raise ValueError("Ollama model cannot be empty.")
        if not 0 < self.timeout <= 120:
            raise ValueError("Ollama timeout must be between 0 and 120 seconds.")

    @property
    def generate_url(self) -> str:
        parts = urlsplit(self.endpoint)
        base_path = parts.path.rstrip("/")
        return urlunsplit((parts.scheme, parts.netloc, f"{base_path}/api/generate", "", ""))

    def generate_json(self, prompt: str) -> Mapping[str, Any]:
        result = self.transport.post_json(
            self.generate_url,
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "format": _PLAN_SCHEMA,
                "options": {"temperature": 0},
            },
            self.timeout,
        )
        response = result.get("response")
        if isinstance(response, str) and not response.strip():
            # Reasoning models can place schema-constrained JSON in Ollama's
            # separate thinking field and leave response empty.
            response = result.get("thinking")
        if not isinstance(response, str):
            raise OllamaError("استجابة Ollama لا تحتوي على حقل response نصي.")
        response = response.strip()
        if response.startswith("```"):
            lines = response.splitlines()
            response = "\n".join(lines[1:-1]).removeprefix("json").strip()
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError as exc:
            raise OllamaError("لم يُرجع Ollama خطة JSON صالحة.") from exc
        if not isinstance(parsed, dict):
            raise OllamaError("يجب أن تكون خطة Ollama كائن JSON.")
        return parsed
