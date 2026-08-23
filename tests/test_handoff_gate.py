import pytest

from livekit.agents import ConversationItemAddedEvent
from livekit.agents.llm import ChatMessage, ToolError

from agent import agent as agent_module
from agent.agent import (
    WayPointAssistant,
    WaypointSessionState,
    attach_confirmation_tracking,
    is_explicit_handoff_request,
)


@pytest.mark.parametrize(
    "text",
    [
        "I want to speak to a human about APP001.",
        "Please connect me to a human.",
        "Connect me to an agent.",
        "I need a representative.",
        "Human support please.",
        "Customer service please.",
        "This is not working; connect me to a human.",
        "I don't understand this; please connect me to a person.",
        "Could you transfer me to customer service?",
        "Can I talk to a representative?",
        "To a human.",
    ],
)
def test_explicit_handoff_classifier_accepts_direct_requests(text: str) -> None:
    assert is_explicit_handoff_request(text)


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "Could you change the travel date to",
        "Actually, I wanted you to change the date.",
        "I'm confused about APP004's status.",
        "Yes.",
        "Okay.",
        "Do you have human agents?",
        "What does human support mean?",
        "Do I need a human?",
        "I want to know what a support agent does.",
        "I would like to learn how human support works.",
        "I don't want to speak to a human.",
        "Please don't connect me to a human.",
        "I cannot talk to a representative right now.",
        "I do not need a human.",
        "I want to not talk to an agent.",
        "I'm not asking for a human.",
        "I want a human, but not yet.",
        "Maybe later.",
    ],
)
def test_explicit_handoff_classifier_rejects_non_requests(
    text: str | None,
) -> None:
    assert not is_explicit_handoff_request(text)


class RecordingSession:
    def __init__(self, userdata: WaypointSessionState) -> None:
        self.userdata = userdata
        self.callbacks = {}

    def on(self, event_name: str, callback=None):
        if callback is None:
            return lambda registered: self.on(event_name, registered)

        self.callbacks[event_name] = callback
        return callback

    def add_message(self, role: str, text: str) -> None:
        self.callbacks["conversation_item_added"](
            ConversationItemAddedEvent(
                item=ChatMessage(role=role, content=[text]),
            )
        )


def test_latest_final_user_turn_replaces_prior_handoff_request() -> None:
    state = WaypointSessionState()
    session = RecordingSession(state)
    attach_confirmation_tracking(session)

    session.add_message("user", "Connect me to a human about APP004.")
    assert state.latest_final_user_text == "Connect me to a human about APP004."

    session.add_message("assistant", "I can help with that.")
    assert state.latest_final_user_text == "Connect me to a human about APP004."

    session.add_message("user", "Actually, I wanted you to change the date.")
    assert state.latest_final_user_text == (
        "Actually, I wanted you to change the date."
    )


class FakeResponse:
    def __init__(self, status: int, payload: dict) -> None:
        self.status = status
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def json(self) -> dict:
        return self.payload


class RecordingHttpSession:
    def __init__(self) -> None:
        self.post_calls: list[dict] = []

    def post(self, url: str, **kwargs) -> FakeResponse:
        self.post_calls.append({"url": url, **kwargs})
        return FakeResponse(
            201,
            {
                "handoff_id": "HOF-test123",
                "application_id": "APP001",
                "reason_code": "user_request",
                "status": "requested",
            },
        )


class FakeRunContext:
    def __init__(self, userdata: WaypointSessionState) -> None:
        self.userdata = userdata
        self.disallow_interruptions_calls = 0

    def disallow_interruptions(self) -> None:
        self.disallow_interruptions_calls += 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("latest_user_text", "reason_code"),
    [
        ("Could you change the travel date to", "repeated_clarification_failure"),
        ("Actually, I wanted you to change the date.", "user_request"),
        ("I'm confused about APP004's status.", "user_request"),
        ("Do you have human agents?", "user_request"),
        ("I want to know what a support agent does.", "user_request"),
        ("Please don't connect me to a human.", "user_request"),
    ],
)
async def test_handoff_rejects_non_requests_before_any_side_effect(
    monkeypatch: pytest.MonkeyPatch,
    latest_user_text: str,
    reason_code: str,
) -> None:
    state = WaypointSessionState(latest_final_user_text=latest_user_text)
    context = FakeRunContext(state)
    http_session = RecordingHttpSession()
    monkeypatch.setattr(
        agent_module.utils.http_context,
        "http_session",
        lambda: http_session,
    )

    with pytest.raises(ToolError, match="explicitly requested"):
        await WayPointAssistant().handoff_to_human(
            context,
            application_id="APP004",
            reason_code=reason_code,
        )

    assert context.disallow_interruptions_calls == 0
    assert http_session.post_calls == []


@pytest.mark.asyncio
async def test_handoff_rejects_automatic_reason_before_any_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = WaypointSessionState(
        latest_final_user_text="Connect me to a human about APP001."
    )
    context = FakeRunContext(state)
    http_session = RecordingHttpSession()
    monkeypatch.setattr(
        agent_module.utils.http_context,
        "http_session",
        lambda: http_session,
    )

    with pytest.raises(ToolError, match="reason_code user_request"):
        await WayPointAssistant().handoff_to_human(
            context,
            application_id="APP001",
            reason_code="repeated_clarification_failure",
        )

    assert context.disallow_interruptions_calls == 0
    assert http_session.post_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "latest_user_text",
    [
        "I want to speak to a human about APP001.",
        "This is not working; connect me to a human about APP001.",
    ],
)
async def test_explicit_handoff_creates_exactly_one_request(
    monkeypatch: pytest.MonkeyPatch,
    latest_user_text: str,
) -> None:
    state = WaypointSessionState(
        latest_final_user_text=latest_user_text
    )
    context = FakeRunContext(state)
    http_session = RecordingHttpSession()
    monkeypatch.setattr(
        agent_module.utils.http_context,
        "http_session",
        lambda: http_session,
    )

    result = await WayPointAssistant().handoff_to_human(
        context,
        application_id="a p p zero zero one",
        reason_code="user_request",
    )

    assert result == {
        "handoff_id": "HOF-test123",
        "application_id": "APP001",
        "reason_code": "user_request",
        "status": "requested",
    }
    assert context.disallow_interruptions_calls == 1
    assert len(http_session.post_calls) == 1
    assert http_session.post_calls[0]["url"].endswith(
        "/applications/APP001/handoffs"
    )
    assert http_session.post_calls[0]["json"] == {
        "reason_code": "user_request"
    }
