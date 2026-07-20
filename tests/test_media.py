import json
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from future_assistant.media import (
    MediaLookupError,
    UrllibYouTubeSearchTransport,
    YouTubeMediaResolver,
)


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *args) -> None:  # noqa: ANN002
        return None

    def read(self, amount: int) -> bytes:
        return self.body[:amount]


def test_official_search_request_keeps_key_out_of_url() -> None:
    requests = []

    def opener(request, *, timeout):  # noqa: ANN001
        requests.append((request, timeout))
        return FakeResponse({"items": [{"id": {"videoId": "dQw4w9WgXcQ"}}]})

    transport = UrllibYouTubeSearchTransport(opener)

    video_id = transport.first_video_id("Arabic song", "private-api-key", 3.0)

    assert video_id == "dQw4w9WgXcQ"
    request, timeout = requests[0]
    assert timeout == 3.0
    assert request.full_url.startswith("https://www.googleapis.com/youtube/v3/search?")
    assert "private-api-key" not in request.full_url
    headers = {key.casefold(): value for key, value in request.header_items()}
    assert headers["x-goog-api-key"] == "private-api-key"
    query = parse_qs(urlsplit(request.full_url).query)
    assert query["part"] == ["snippet"]
    assert query["type"] == ["video"]
    assert query["maxResults"] == ["1"]
    assert query["q"] == ["Arabic song"]


class CountingTransport:
    def __init__(self, result: str | None = None, *, fail: bool = False) -> None:
        self.result = result
        self.fail = fail
        self.calls = 0

    def first_video_id(self, query: str, api_key: str, timeout: float) -> str | None:
        self.calls += 1
        if self.fail:
            raise RuntimeError(f"failure containing {api_key}")
        return self.result


def test_missing_key_uses_results_without_network_call() -> None:
    transport = CountingTransport("dQw4w9WgXcQ")
    fallback = "https://www.youtube.com/results?search_query=test"
    resolver = YouTubeMediaResolver(None, transport=transport)

    assert resolver.youtube_url("test", fallback) == fallback
    assert transport.calls == 0


@pytest.mark.parametrize("result", [None, "", "invalid", "dQw4w9WgXcQextra"])
def test_missing_or_invalid_video_id_uses_results(result: str | None) -> None:
    fallback = "https://www.youtube.com/results?search_query=test"
    resolver = YouTubeMediaResolver("key", transport=CountingTransport(result))

    assert resolver.youtube_url("test", fallback) == fallback


def test_api_failure_uses_results_and_does_not_expose_key() -> None:
    fallback = "https://www.youtube.com/results?search_query=test"
    resolver = YouTubeMediaResolver(
        "private-api-key",
        transport=CountingTransport(fail=True),
    )

    assert resolver.youtube_url("test", fallback) == fallback
    assert "private-api-key" not in repr(resolver)


def test_transport_wraps_network_errors_without_sensitive_details() -> None:
    def opener(request, *, timeout):  # noqa: ANN001
        raise URLError("private-api-key")

    transport = UrllibYouTubeSearchTransport(opener)

    with pytest.raises(MediaLookupError) as caught:
        transport.first_video_id("test", "private-api-key", 3.0)

    assert "private-api-key" not in str(caught.value)
