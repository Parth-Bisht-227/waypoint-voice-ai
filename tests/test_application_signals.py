from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from livekit.agents.llm import ToolError

from agent import agent as agent_module
from agent.agent import WayPointAssistant, WaypointSessionState
from agent.application_signals import (
    APPLICATION_SIGNAL_TOPIC,
    make_application_signal_sender,
)


class FakeResponse:
    def __init__(
        self,
        status: int,
        payload: dict,
        events: list[tuple],
        operation: str,
    ) -> None:
        self.status = status
        self.payload = payload
        self.events = events
        self.operation = operation

    async def __aenter__(self):
        self.events.append((f"{self.operation}_entered",))
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def json(self) -> dict:
        self.events.append((f"{self.operation}_json",))
        return self.payload


class RecordingHttpSession:
    def __init__(
        self,
        events: list[tuple],
        *,
        get_status: int = 200,
        patch_status: int = 200,
        post_status: int = 201,
    ) -> None:
        self.events = events
        self.get_status = get_status
        self.patch_status = patch_status
        self.post_status = post_status

    def get(self, url: str, *, timeout: int) -> FakeResponse:
        self.events.append(("get_requested", url, timeout))
        if url.endswith("/missing-documents"):
            payload = {
                "application_id": "APP001",
                "missing_documents": ["bank_statement"],
            }
        else:
            payload = {
                "application_id": "APP001",
                "destination": "Solara",
                "status": "blocked",
                "travel_date": "2026-11-20",
            }
        return FakeResponse(
            self.get_status,
            payload,
            self.events,
            "get",
        )

    def patch(
        self,
        url: str,
        *,
        json: dict,
        timeout: int,
    ) -> FakeResponse:
        self.events.append(("patch_requested", url, json, timeout))
        return FakeResponse(
            self.patch_status,
            {
                "application_id": "APP001",
                "old_date": "2026-11-20",
                "new_date": json["new_date"],
                "changed": True,
            },
            self.events,
            "patch",
        )

    def post(
        self,
        url: str,
        *,
        json: dict,
        timeout: int,
    ) -> FakeResponse:
        self.events.append(("post_requested", url, json, timeout))
        return FakeResponse(
            self.post_status,
            {
                "application_id": "APP005",
                "destination": json["destination"],
                "status": "processing",
                "travel_date": json["travel_date"],
            },
            self.events,
            "post",
        )


class RecordingParticipant:
    def __init__(self, events: list[tuple]) -> None:
        self.events = events

    async def publish_data(
        self,
        payload: bytes,
        *,
        reliable: bool,
        topic: str,
    ) -> None:
        self.events.append(("publish", payload, reliable, topic))


class FakeRunContext:
    def __init__(
        self,
        userdata: WaypointSessionState,
        events: list[tuple],
    ) -> None:
        self.userdata = userdata
        self.events = events

    def disallow_interruptions(self) -> None:
        self.events.append(("disallow_interruptions",))


def state_with_livekit_sender(
    events: list[tuple],
) -> WaypointSessionState:
    participant = RecordingParticipant(events)
    job_context = SimpleNamespace(
        room=SimpleNamespace(local_participant=participant),
    )
    return WaypointSessionState(
        application_signal_sender=make_application_signal_sender(job_context),
    )


def install_http_session(
    monkeypatch: pytest.MonkeyPatch,
    events: list[tuple],
    *,
    get_status: int = 200,
    patch_status: int = 200,
    post_status: int = 201,
) -> RecordingHttpSession:
    session = RecordingHttpSession(
        events,
        get_status=get_status,
        patch_status=patch_status,
        post_status=post_status,
    )
    monkeypatch.setattr(
        agent_module.utils.http_context,
        "http_session",
        lambda: session,
    )
    return session


@pytest.mark.asyncio
async def test_livekit_sender_uses_exact_id_only_contract() -> None:
    events: list[tuple] = []
    state = state_with_livekit_sender(events)

    await state.application_signal_sender("application_context", "APP001")

    assert events == [
        (
            "publish",
            b'{"type":"application_context","application_id":"APP001"}',
            True,
            APPLICATION_SIGNAL_TOPIC,
        )
    ]


@pytest.mark.asyncio
async def test_authoritative_read_tools_publish_context_after_http_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []
    install_http_session(monkeypatch, events)
    state = state_with_livekit_sender(events)
    context = FakeRunContext(state, events)
    assistant = WayPointAssistant()

    status = await assistant.get_application_status(
        context,
        application_id="app001",
    )

    assert status == {
        "application_id": "APP001",
        "destination": "Solara",
        "status": "blocked",
        "travel_date": "2026-11-20",
    }
    assert [event[0] for event in events] == [
        "get_requested",
        "get_entered",
        "get_json",
        "publish",
    ]
    assert events[-1][1] == (
        b'{"type":"application_context","application_id":"APP001"}'
    )

    events.clear()
    missing = await assistant.get_missing_documents(
        context,
        application_id="APP001",
    )

    assert missing == {
        "application_id": "APP001",
        "missing_documents": ["bank_statement"],
    }
    assert [event[0] for event in events] == [
        "get_requested",
        "get_entered",
        "get_json",
        "publish",
    ]
    assert events[-1][1] == (
        b'{"type":"application_context","application_id":"APP001"}'
    )


@pytest.mark.asyncio
async def test_create_application_publishes_new_context_after_http_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []
    install_http_session(monkeypatch, events)
    state = state_with_livekit_sender(events)
    context = FakeRunContext(state, events)
    travel_date = (date.today() + timedelta(days=90)).isoformat()

    result = await WayPointAssistant().create_travel_application(
        context,
        destination="Japan",
        travel_date=travel_date,
    )

    assert result == {
        "application_id": "APP005",
        "status": "processing",
    }
    assert [event[0] for event in events] == [
        "disallow_interruptions",
        "post_requested",
        "post_entered",
        "post_json",
        "publish",
    ]
    assert events[1][2] == {
        "destination": "Japan",
        "travel_date": travel_date,
    }
    assert events[-1] == (
        "publish",
        b'{"type":"application_context","application_id":"APP005"}',
        True,
        APPLICATION_SIGNAL_TOPIC,
    )


@pytest.mark.asyncio
async def test_failed_application_creation_publishes_no_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []
    install_http_session(monkeypatch, events, post_status=500)
    state = state_with_livekit_sender(events)
    context = FakeRunContext(state, events)
    travel_date = (date.today() + timedelta(days=90)).isoformat()

    with pytest.raises(ToolError, match="created safely"):
        await WayPointAssistant().create_travel_application(
            context,
            destination="Japan",
            travel_date=travel_date,
        )

    assert "publish" not in [event[0] for event in events]


@pytest.mark.asyncio
async def test_prepare_publishes_context_only_after_application_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []
    install_http_session(monkeypatch, events)
    state = state_with_livekit_sender(events)
    context = FakeRunContext(state, events)
    proposed_date = (date.today() + timedelta(days=90)).isoformat()

    result = await WayPointAssistant().prepare_travel_date_change(
        context,
        application_id="APP001",
        new_date=proposed_date,
    )

    assert result["status"] == "confirmation_required"
    assert state.pending_application_id == "APP001"
    assert state.pending_travel_date == proposed_date
    assert [event[0] for event in events] == [
        "get_requested",
        "get_entered",
        "get_json",
        "publish",
    ]
    assert events[-1][1] == (
        b'{"type":"application_context","application_id":"APP001"}'
    )


@pytest.mark.asyncio
async def test_apply_publishes_updated_only_after_successful_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []
    install_http_session(monkeypatch, events)
    state = state_with_livekit_sender(events)
    proposed_date = (date.today() + timedelta(days=90)).isoformat()
    state.pending_application_id = "APP001"
    state.pending_travel_date = proposed_date
    state.pending_idempotency_key = "date-test"
    context = FakeRunContext(state, events)

    result = await WayPointAssistant().apply_pending_travel_date_change(context)

    assert result == {
        "application_id": "APP001",
        "old_date": "2026-11-20",
        "new_date": proposed_date,
        "changed": True,
    }
    assert [event[0] for event in events] == [
        "disallow_interruptions",
        "patch_requested",
        "patch_entered",
        "patch_json",
        "publish",
    ]
    assert events[-1] == (
        "publish",
        b'{"type":"application_updated","application_id":"APP001"}',
        True,
        APPLICATION_SIGNAL_TOPIC,
    )
    assert state.pending_application_id is None
    assert state.pending_travel_date is None
    assert state.pending_idempotency_key is None


@pytest.mark.asyncio
async def test_failed_operations_publish_no_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []
    install_http_session(monkeypatch, events, patch_status=500)
    state = state_with_livekit_sender(events)
    state.pending_application_id = "APP001"
    state.pending_travel_date = (date.today() + timedelta(days=90)).isoformat()
    state.pending_idempotency_key = "date-test"
    context = FakeRunContext(state, events)
    assistant = WayPointAssistant()


    with pytest.raises(ToolError, match="safely complete"):
        await assistant.apply_pending_travel_date_change(context)
    assert "publish" not in [event[0] for event in events]

    events.clear()
    install_http_session(monkeypatch, events, get_status=500)
    with pytest.raises(ToolError, match="temporarily unavailable"):
        await assistant.get_application_status(context, application_id="APP001")
    assert "publish" not in [event[0] for event in events]


@pytest.mark.asyncio
async def test_publisher_failure_does_not_replace_successful_mutation_result(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    events: list[tuple] = []
    install_http_session(monkeypatch, events)

    async def failing_sender(signal_type: str, application_id: str) -> None:
        events.append(("publish_attempt", signal_type, application_id))
        raise RuntimeError("room closed")

    proposed_date = (date.today() + timedelta(days=90)).isoformat()
    state = WaypointSessionState(
        pending_application_id="APP001",
        pending_travel_date=proposed_date,
        pending_idempotency_key="date-test",
        application_signal_sender=failing_sender,
    )
    context = FakeRunContext(state, events)

    with caplog.at_level("ERROR", logger="agent.application_signals"):
        result = await WayPointAssistant().apply_pending_travel_date_change(
            context
        )

    assert result["application_id"] == "APP001"
    assert result["new_date"] == proposed_date
    assert result["changed"] is True
    assert [event[0] for event in events][-2:] == [
        "patch_json",
        "publish_attempt",
    ]
    assert "failed to publish application signal" in caplog.text
    assert state.pending_application_id is None


@pytest.mark.asyncio
async def test_default_session_state_needs_no_signal_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple] = []
    install_http_session(monkeypatch, events)
    state = WaypointSessionState()

    result = await WayPointAssistant().get_application_status(
        FakeRunContext(state, events),
        application_id="APP001",
    )

    assert result["application_id"] == "APP001"
    assert [event[0] for event in events] == [
        "get_requested",
        "get_entered",
        "get_json",
    ]
