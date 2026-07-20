from urllib.request import Request

import pytest

from future_assistant.updates import TransportSecurityError
from future_assistant.updates.transport import _HttpsOnlyRedirectHandler


def test_network_transport_blocks_https_to_http_before_following_redirect() -> None:
    handler = _HttpsOnlyRedirectHandler()

    with pytest.raises(TransportSecurityError):
        handler.redirect_request(
            Request("https://updates.example.test/manifest.json"),
            None,  # type: ignore[arg-type]
            302,
            "Found",
            {},
            "http://mirror.example.test/manifest.json",
        )
