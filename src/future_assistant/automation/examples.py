"""Reference executors that expose typed effects instead of raw shell access."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from typing import Protocol
from urllib.parse import urlencode, urlsplit, urlunsplit

from .cancellation import CancellationToken
from .errors import AutomationConfigurationError, InvalidArgumentsError
from .models import Permission, RiskLevel, SkillManifest

_APP_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class BrowserEffects(Protocol):
    async def open_url(self, url: str) -> None: ...


class AppEffects(Protocol):
    async def launch_app(self, app_id: str) -> None: ...


BROWSER_SEARCH_MANIFEST = SkillManifest(
    skill_id="browser.search",
    executor_id="builtin.browser_search",
    version="1.0.0",
    name="Search the web",
    description="Open a search query through a fixed HTTPS provider.",
    permissions=frozenset({Permission.BROWSER_OPEN_URL}),
    risk_level=RiskLevel.LOW,
    timeout_seconds=10.0,
)

APP_LAUNCH_MANIFEST = SkillManifest(
    skill_id="app.launch",
    executor_id="builtin.app_launch",
    version="1.0.0",
    name="Launch an application",
    description="Launch an application by an allowlisted identifier, never by a command string.",
    permissions=frozenset({Permission.APP_LAUNCH}),
    risk_level=RiskLevel.HIGH,
    timeout_seconds=10.0,
)


def _require_exact_keys(arguments: Mapping[str, object], expected: set[str]) -> None:
    actual = set(arguments)
    if actual != expected:
        raise InvalidArgumentsError(
            f"Expected arguments {sorted(expected)!r}; received {sorted(actual)!r}."
        )


class BrowserSearchExecutor:
    executor_id = BROWSER_SEARCH_MANIFEST.executor_id
    permissions = BROWSER_SEARCH_MANIFEST.permissions

    def __init__(
        self,
        effects: BrowserEffects,
        *,
        search_endpoint: str = "https://www.google.com/search",
        allowed_hosts: Collection[str] = ("www.google.com",),
        max_query_length: int = 300,
    ) -> None:
        hosts = frozenset(host.rstrip(".").casefold() for host in allowed_hosts)
        try:
            parts = urlsplit(search_endpoint)
            port = parts.port
        except ValueError as exc:
            raise AutomationConfigurationError("Search endpoint is invalid.") from exc
        host = (parts.hostname or "").rstrip(".").casefold()
        if (
            parts.scheme.casefold() != "https"
            or not host
            or host not in hosts
            or parts.username is not None
            or parts.password is not None
            or port not in {None, 443}
            or parts.query
            or parts.fragment
        ):
            raise AutomationConfigurationError(
                "Search endpoint must be a clean HTTPS URL on an explicitly allowed host."
            )
        if isinstance(max_query_length, bool) or not 1 <= max_query_length <= 1000:
            raise AutomationConfigurationError("max_query_length must be between 1 and 1000.")
        self._effects = effects
        self._endpoint = search_endpoint
        self._max_query_length = max_query_length

    def validate(self, arguments: Mapping[str, object]) -> None:
        self._query(arguments)

    async def execute(
        self,
        arguments: Mapping[str, object],
        cancellation: CancellationToken,
    ) -> Mapping[str, object]:
        query = self._query(arguments)
        cancellation.raise_if_cancelled()
        parts = urlsplit(self._endpoint)
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode({"q": query}), ""))
        await self._effects.open_url(url)
        cancellation.raise_if_cancelled()
        return {"opened": True, "provider": parts.hostname or ""}

    def _query(self, arguments: Mapping[str, object]) -> str:
        _require_exact_keys(arguments, {"query"})
        value = arguments["query"]
        if not isinstance(value, str):
            raise InvalidArgumentsError("query must be a string.")
        if any(ord(character) < 32 for character in value):
            raise InvalidArgumentsError("query cannot contain control characters.")
        query = " ".join(value.split())
        if not query or len(query) > self._max_query_length:
            raise InvalidArgumentsError(
                f"query must contain 1-{self._max_query_length} characters."
            )
        return query


class AppLaunchExecutor:
    executor_id = APP_LAUNCH_MANIFEST.executor_id
    permissions = APP_LAUNCH_MANIFEST.permissions

    def __init__(self, effects: AppEffects, *, allowed_app_ids: Collection[str]) -> None:
        app_ids = frozenset(allowed_app_ids)
        if not app_ids or not all(
            isinstance(app_id, str) and _APP_ID.fullmatch(app_id) for app_id in app_ids
        ):
            raise AutomationConfigurationError(
                "allowed_app_ids must contain safe application identifiers."
            )
        self._effects = effects
        self._allowed_app_ids = app_ids

    def validate(self, arguments: Mapping[str, object]) -> None:
        self._app_id(arguments)

    async def execute(
        self,
        arguments: Mapping[str, object],
        cancellation: CancellationToken,
    ) -> Mapping[str, object]:
        app_id = self._app_id(arguments)
        cancellation.raise_if_cancelled()
        await self._effects.launch_app(app_id)
        cancellation.raise_if_cancelled()
        return {"launched": True, "app_id": app_id}

    def _app_id(self, arguments: Mapping[str, object]) -> str:
        _require_exact_keys(arguments, {"app_id"})
        app_id = arguments["app_id"]
        if not isinstance(app_id, str) or app_id not in self._allowed_app_ids:
            raise InvalidArgumentsError("app_id is not in the application allowlist.")
        return app_id
