import pytest

from livekit.agents.llm import ToolError

from agent import agent as agent_module
from agent.agent import WayPointAssistant, WaypointSessionState


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
async def test_explicit_handoff_creates_exactly_one_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = FakeRunContext(WaypointSessionState())
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


@pytest.mark.asyncio
async def test_handoff_rejects_invalid_application_id_before_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = FakeRunContext(WaypointSessionState())
    http_session = RecordingHttpSession()
    monkeypatch.setattr(
        agent_module.utils.http_context,
        "http_session",
        lambda: http_session,
    )

    with pytest.raises(ToolError, match="application ID"):
        await WayPointAssistant().handoff_to_human(
            context,
            application_id="unknown",
            reason_code="user_request",
        )

    assert context.disallow_interruptions_calls == 0
    assert http_session.post_calls == []
