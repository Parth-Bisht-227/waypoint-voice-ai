from __future__ import annotations

from datetime import date, timedelta

import pytest
from livekit.agents import ConversationItemAddedEvent
from livekit.agents.llm import ChatMessage, ToolError

from agent import agent as agent_module
from agent.agent import (
    WayPointAssistant,
    WaypointSessionState,
    attach_confirmation_tracking,
    is_explicit_confirmation,
)


@pytest.mark.parametrize(
    "text",
    [
        "yes",
        "Yes.",
        "I confirm",
        "confirm it",
        "please apply it",
        "yes, apply it",
        "go ahead and apply it",
        "yes, change it",
    ],
)
def test_explicit_confirmation_accepts_complete_confirmation_utterances(
    text: str,
) -> None:
    assert is_explicit_confirmation(text)


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "that's great",
        "okay",
        "sure",
        "no",
        "wait",
        "actually, use December 26 instead",
        "yes, but wait",
        "yes, change it to December 26",
        "what is the status of APP001?",
    ],
)
def test_explicit_confirmation_rejects_vague_negative_or_corrective_input(
    text: str | None,
) -> None:
    assert not is_explicit_confirmation(text)


class RecordingSession:
    def __init__(self, userdata: WaypointSessionState) -> None:
        self.userdata = userdata
        self.callbacks = {}

    def on(self, event_name, callback):
        self.callbacks[event_name] = callback
        return callback

    def add_message(self, role: str, text: str) -> None:
        self.callbacks["conversation_item_added"](
            ConversationItemAddedEvent(
                item=ChatMessage(role=role, content=[text]),
            )
        )


def test_confirmation_tracking_uses_only_finalized_user_messages() -> None:
    state = WaypointSessionState()
    session = RecordingSession(state)
    attach_confirmation_tracking(session)

    session.add_message("assistant", "Yes.")
    assert not state.pending_confirmation_granted

    # A confirmation cannot be granted before a proposal exists.
    session.add_message("user", "Yes.")
    assert not state.pending_confirmation_granted

    state.pending_application_id = "APP001"
    state.pending_travel_date = "2026-12-25"
    state.pending_idempotency_key = "date-test"

    session.add_message("user", "Yes.")
    assert state.pending_confirmation_granted

    session.add_message("assistant", "I will apply it.")
    assert state.pending_confirmation_granted

    session.add_message("user", "Actually, use December 26 instead.")
    assert not state.pending_confirmation_granted


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
        self.patch_calls: list[dict] = []

    def get(self, url: str, *, timeout: int) -> FakeResponse:
        return FakeResponse(
            200,
            {
                "application_id": "APP001",
                "travel_date": "2026-11-20",
            },
        )

    def patch(
        self,
        url: str,
        *,
        json: dict,
        timeout: int,
    ) -> FakeResponse:
        self.patch_calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            200,
            {
                "application_id": "APP001",
                "old_date": "2026-11-20",
                "new_date": json["new_date"],
                "changed": True,
            },
        )


class FakeRunContext:
    def __init__(self, userdata: WaypointSessionState) -> None:
        self.userdata = userdata
        self.disallow_interruptions_calls = 0

    def disallow_interruptions(self) -> None:
        self.disallow_interruptions_calls += 1


@pytest.mark.asyncio
async def test_apply_requires_later_explicit_confirmation_before_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = WaypointSessionState()
    conversation = RecordingSession(state)
    attach_confirmation_tracking(conversation)
    context = FakeRunContext(state)
    http_session = RecordingHttpSession()
    monkeypatch.setattr(
        agent_module.utils.http_context,
        "http_session",
        lambda: http_session,
    )
    assistant = WayPointAssistant()
    proposed_date = (date.today() + timedelta(days=90)).isoformat()

    # The request and prepare call occur in the same finalized user turn.
    conversation.add_message(
        "user",
        f"Change APP001 to {proposed_date}.",
    )
    prepared = await assistant.prepare_travel_date_change(
        context,
        application_id="APP001",
        new_date=proposed_date,
    )
    assert prepared["status"] == "confirmation_required"
    assert not state.pending_confirmation_granted
    pending_idempotency_key = state.pending_idempotency_key
    assert pending_idempotency_key is not None

    with pytest.raises(ToolError, match="confirm"):
        await assistant.apply_pending_travel_date_change(context)
    assert http_session.patch_calls == []
    assert context.disallow_interruptions_calls == 0
    assert state.pending_idempotency_key == pending_idempotency_key

    # A later but vague user turn still grants no mutation authority.
    conversation.add_message("user", "That's great.")
    with pytest.raises(ToolError, match="confirm"):
        await assistant.apply_pending_travel_date_change(context)
    assert http_session.patch_calls == []
    assert context.disallow_interruptions_calls == 0
    assert state.pending_idempotency_key == pending_idempotency_key

    # A later explicit bare "yes" authorizes exactly one backend mutation.
    conversation.add_message("user", "Yes.")
    result = await assistant.apply_pending_travel_date_change(context)

    assert result["application_id"] == "APP001"
    assert result["new_date"] == proposed_date
    assert len(http_session.patch_calls) == 1
    assert (
        http_session.patch_calls[0]["json"]["idempotency_key"]
        == pending_idempotency_key
    )
    assert context.disallow_interruptions_calls == 1
    assert state.pending_application_id is None
    assert state.pending_travel_date is None
    assert state.pending_idempotency_key is None
    assert not state.pending_confirmation_granted
