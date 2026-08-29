import time

import pytest
from livekit.agents import ErrorEvent
from livekit.agents.llm import LLMError

from agent.session_resilience import (
    LLM_FAILURE_MESSAGES,
    attach_llm_failure_handler,
    schedule_latency_filler,
)


class RecordingSession:
    def __init__(self) -> None:
        self.agent_state = "thinking"
        self.user_state = "listening"
        self.callbacks = {}
        self.spoken: list[dict] = []

    def on(self, event_name, callback):
        self.callbacks[event_name] = callback

    def say(self, text: str, **kwargs):
        self.spoken.append({"text": text, **kwargs})


def llm_error_event(*, recoverable: bool) -> ErrorEvent:
    return ErrorEvent(
        error=LLMError(
            timestamp=time.time(),
            label="test-llm",
            error=RuntimeError("provider unavailable"),
            recoverable=recoverable,
        ),
        source=object(),
    )


@pytest.mark.asyncio
async def test_latency_filler_only_speaks_while_thinking() -> None:
    session = RecordingSession()

    await schedule_latency_filler(session, ("One moment.",), delay=0)
    assert session.spoken[0]["text"] == "One moment."
    assert session.spoken[0]["add_to_chat_ctx"] is False

    session.spoken.clear()
    session.agent_state = "speaking"
    await schedule_latency_filler(session, ("One moment.",), delay=0)
    assert session.spoken == []


def test_terminal_llm_error_speaks_a_recovery_message() -> None:
    session = RecordingSession()
    attach_llm_failure_handler(session)

    session.callbacks["error"](llm_error_event(recoverable=True))
    assert session.spoken == []

    session.callbacks["error"](llm_error_event(recoverable=False))
    assert session.spoken[0]["text"] in LLM_FAILURE_MESSAGES
    assert session.spoken[0]["add_to_chat_ctx"] is False
