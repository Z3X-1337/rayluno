"""Optional, privacy-conscious media lookup through the official YouTube API."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .identity import environment_value

_YOUTUBE_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
_YOUTUBE_WATCH_ENDPOINT = "https://www.youtube.com/watch"
_MAX_RESPONSE_BYTES = 1_000_000
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class MediaLookupError(RuntimeError):
    """A deliberately non-sensitive error raised by the official API transport."""


class YouTubeSearchTransport(Protocol):
    def first_video_id(self, query: str, api_key: str, timeout: float) -> str | None: ...


class MediaResolver(Protocol):
    def youtube_url(self, query: str, fallback_url: str) -> str: ...


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):  # noqa: ANN001
        return None


def _secure_urlopen(request: Request, *, timeout: float):  # noqa: ANN202
    # The API key is a header, so rejecting redirects guarantees it is sent only
    # to the fixed Google API origin below.
    return build_opener(_RejectRedirects()).open(request, timeout=timeout)


class UrllibYouTubeSearchTransport:
    """Small standard-library client for YouTube Data API ``search.list``."""

    def __init__(self, opener: Callable[..., Any] | None = None) -> None:
        self._opener = opener or _secure_urlopen

    def first_video_id(self, query: str, api_key: str, timeout: float) -> str | None:
        parameters = urlencode(
            {
                "part": "snippet",
                "type": "video",
                "maxResults": "1",
                "safeSearch": "moderate",
                "fields": "items/id/videoId",
                "q": query,
            }
        )
        request = Request(
            f"{_YOUTUBE_SEARCH_ENDPOINT}?{parameters}",
            headers={
                "Accept": "application/json",
                # Keeping the BYOK key out of the URL prevents it from leaking into
                # browser history, proxy logs, and exception URLs.
                "X-Goog-Api-Key": api_key,
            },
            method="GET",
        )
        try:
            with self._opener(request, timeout=timeout) as response:
                body = response.read(_MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError):
            raise MediaLookupError("YouTube lookup failed.") from None

        if len(body) > _MAX_RESPONSE_BYTES:
            raise MediaLookupError("YouTube response exceeded the safe size limit.")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise MediaLookupError("YouTube returned an invalid response.") from None
        return self._extract_video_id(payload)

    @staticmethod
    def _extract_video_id(payload: object) -> str | None:
        if not isinstance(payload, Mapping):
            return None
        items = payload.get("items")
        if not isinstance(items, list) or not items:
            return None
        first = items[0]
        if not isinstance(first, Mapping):
            return None
        identifier = first.get("id")
        if not isinstance(identifier, Mapping):
            return None
        video_id = identifier.get("videoId")
        return video_id if isinstance(video_id, str) else None


class YouTubeMediaResolver:
    """Resolve a query to a watch URL, falling back to safe search results."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 4.0,
        transport: YouTubeSearchTransport | None = None,
    ) -> None:
        cleaned_key = api_key.strip() if isinstance(api_key, str) else ""
        # An absurdly large value is not a usable API key and should never be sent.
        self._api_key = cleaned_key if 0 < len(cleaned_key) <= 512 else None
        self._timeout = timeout if 0 < timeout <= 15 else 4.0
        self._transport = transport or UrllibYouTubeSearchTransport()

    @classmethod
    def from_env(cls) -> YouTubeMediaResolver:
        return cls(environment_value("YOUTUBE_API_KEY"))

    def youtube_url(self, query: str, fallback_url: str) -> str:
        if self._api_key is None:
            return fallback_url
        try:
            video_id = self._transport.first_video_id(query, self._api_key, self._timeout)
        except Exception:  # API/transport boundary: every failure must degrade to search.
            return fallback_url
        if not isinstance(video_id, str) or _VIDEO_ID.fullmatch(video_id) is None:
            return fallback_url
        return f"{_YOUTUBE_WATCH_ENDPOINT}?{urlencode({'v': video_id})}"
