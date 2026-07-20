from urllib.parse import parse_qs, urlsplit

import pytest

from future_assistant.actions import ActionFactory
from future_assistant.config import AssistantConfig
from future_assistant.domain import ActionKind, VolumeOperation
from future_assistant.router import DeterministicRouter


@pytest.fixture
def router() -> DeterministicRouter:
    return DeterministicRouter(ActionFactory(AssistantConfig(audit_path=None)))


@pytest.mark.parametrize("phrase", ["الوقت", "كم الساعة", "ما هو الوقت", "الساعة كم"])
def test_routes_time_phrases(router: DeterministicRouter, phrase: str) -> None:
    plan = router.route(phrase)

    assert plan is not None
    assert plan.actions[0].kind is ActionKind.REPORT_TIME


def test_routes_arabic_web_search_with_encoded_query(router: DeterministicRouter) -> None:
    plan = router.route("ابحث لي عن أفضل حاسوب محمول")

    assert plan is not None
    action = plan.actions[0]
    assert action.kind is ActionKind.OPEN_URL
    parsed = urlsplit(action.parameters["url"])
    assert parsed.hostname == "www.google.com"
    assert parse_qs(parsed.query)["q"] == ["افضل حاسوب محمول"]
    assert action.parameters["purpose"] == "search"


@pytest.mark.parametrize(
    ("phrase", "query", "purpose"),
    [
        ("افتح يوتيوب على فيديو تعلم بايثون", "تعلم بايثون", "youtube_media"),
        ("شغل أغنية فيروز على يوتيوب", "فيروز", "youtube_media"),
        ("يوتيوب مراجعة هاتف", "مراجعة هاتف", "youtube_search"),
        ("شغل أغنية نسم علينا الهوى", "نسم علينا الهوي", "youtube_media"),
        ("افتح فيديو وثائقي عن الفضاء", "وثائقي عن الفضاء", "youtube_media"),
    ],
)
def test_routes_youtube_search(
    router: DeterministicRouter,
    phrase: str,
    query: str,
    purpose: str,
) -> None:
    plan = router.route(phrase)

    assert plan is not None
    parsed = urlsplit(plan.actions[0].parameters["url"])
    assert parsed.hostname == "www.youtube.com"
    assert parse_qs(parsed.query)["search_query"] == [query]
    assert plan.actions[0].parameters["purpose"] == purpose
    if purpose == "youtube_media":
        assert plan.actions[0].parameters["media_query"] == query


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("افتح الحاسبة", "calculator"),
        ("شغل المفكرة", "notepad"),
        ("افتح مستكشف الملفات", "file_manager"),
        ("افتح برنامج الرسام", "paint"),
    ],
)
def test_routes_allowlisted_apps(router: DeterministicRouter, phrase: str, expected: str) -> None:
    plan = router.route(phrase)

    assert plan is not None
    assert plan.actions[0].kind is ActionKind.OPEN_APP
    assert plan.actions[0].parameters["app_id"] == expected


def test_routes_known_site_and_raw_domain(router: DeterministicRouter) -> None:
    youtube = router.route("افتح يوتيوب")
    raw = router.route("افتح موقع github.com")

    assert youtube is not None
    assert youtube.actions[0].parameters["url"] == "https://www.youtube.com/"
    assert raw is not None
    assert raw.actions[0].parameters["url"] == "https://github.com"


@pytest.mark.parametrize(
    ("phrase", "operation"),
    [
        ("ارفع الصوت", VolumeOperation.UP.value),
        ("وطي الصوت", VolumeOperation.DOWN.value),
        ("اكتم الصوت", VolumeOperation.TOGGLE_MUTE.value),
    ],
)
def test_routes_volume(router: DeterministicRouter, phrase: str, operation: str) -> None:
    plan = router.route(phrase)

    assert plan is not None
    assert plan.actions[0].kind is ActionKind.CONTROL_VOLUME
    assert plan.actions[0].parameters["operation"] == operation


def test_returns_none_for_unknown_or_empty_commands(router: DeterministicRouter) -> None:
    assert router.route("") is None
    assert router.route("اصنع لي مركبة فضائية") is None


@pytest.mark.parametrize(
    ("phrase", "kind", "value"),
    [
        ("what time is it", ActionKind.REPORT_TIME, None),
        ("open calculator", ActionKind.OPEN_APP, "calculator"),
        ("open YouTube", ActionKind.OPEN_URL, "https://www.youtube.com/"),
        ("volume up", ActionKind.CONTROL_VOLUME, VolumeOperation.UP.value),
    ],
)
def test_routes_common_english_commands(
    router: DeterministicRouter,
    phrase: str,
    kind: ActionKind,
    value: str | None,
) -> None:
    plan = router.route(phrase)

    assert plan is not None
    action = plan.actions[0]
    assert action.kind is kind
    if kind is ActionKind.OPEN_APP:
        assert action.parameters["app_id"] == value
    elif kind is ActionKind.OPEN_URL:
        assert action.parameters["url"] == value
    elif kind is ActionKind.CONTROL_VOLUME:
        assert action.parameters["operation"] == value


@pytest.mark.parametrize(
    ("phrase", "query", "purpose"),
    [
        ("search for the best local AI model", "the best local ai model", "search"),
        ("play a song Bohemian Rhapsody", "bohemian rhapsody", "youtube_media"),
        ("open video Python for beginners", "python for beginners", "youtube_media"),
        ("search YouTube for Python tutorial", "python tutorial", "youtube_search"),
    ],
)
def test_routes_english_search_and_media(
    router: DeterministicRouter,
    phrase: str,
    query: str,
    purpose: str,
) -> None:
    plan = router.route(phrase)

    assert plan is not None
    parsed = urlsplit(plan.actions[0].parameters["url"])
    key = "search_query" if parsed.hostname == "www.youtube.com" else "q"
    assert parse_qs(parsed.query)[key] == [query]
    assert plan.actions[0].parameters["purpose"] == purpose
