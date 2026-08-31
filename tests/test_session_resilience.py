import time

from livekit.agents import ErrorEvent
from livekit.agents.llm import LLMError

from agent.session_resilience import (
    LLM_FAILURE_MESSAGES,
    attach_llm_failure_handler,
)


class RecordingSession:
    def __init__(self) -> None:
        self.llm = object()
        self.callbacks = {}
        self.spoken: list[dict] = []

    def on(self, event_name, callback):
        self.callbacks[event_name] = callback

    def say(self, text: str, **kwargs):
        self.spoken.append({"text": text, **kwargs})


def llm_error_event(*, recoverable: bool, source: object) -> ErrorEvent:
    return ErrorEvent(
        error=LLMError(
            timestamp=time.time(),
            label="test-llm",
            error=RuntimeError("provider unavailable"),
            recoverable=recoverable,
        ),
        source=source,
    )


def test_terminal_llm_error_speaks_a_recovery_message() -> None:
    session = RecordingSession()
    attach_llm_failure_handler(session)

    session.callbacks["error"](
        llm_error_event(recoverable=True, source=session.llm)
    )
    assert session.spoken == []

    session.callbacks["error"](
        llm_error_event(recoverable=False, source=object())
    )
    assert session.spoken == []

    session.callbacks["error"](
        llm_error_event(recoverable=False, source=session.llm)
    )
    assert session.spoken[0]["text"] in LLM_FAILURE_MESSAGES
    assert session.spoken[0]["add_to_chat_ctx"] is False
