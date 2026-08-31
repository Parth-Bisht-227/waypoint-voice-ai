"""Recovery handling for terminal LLM failures."""

from __future__ import annotations

import random

from livekit.agents import AgentSession, ErrorEvent
from livekit.agents.llm import LLMError


LLM_FAILURE_MESSAGES = (
    "I'm having trouble responding. Could you say that once more?",
    "Sorry, I hit a brief connection issue. Could you repeat that?",
    "I couldn't complete that response. Please say it once more.",
)


def attach_llm_failure_handler(session: AgentSession) -> None:
    """Speak after the configured LLM or fallback chain is exhausted."""

    def on_error(event: ErrorEvent) -> None:
        if not isinstance(event.error, LLMError) or event.error.recoverable:
            return
        if event.source is not session.llm:
            # An underlying provider may fail while the configured fallback
            # adapter is still able to complete the turn.
            return

        try:
            session.say(
                random.choice(LLM_FAILURE_MESSAGES),
                allow_interruptions=True,
                add_to_chat_ctx=False,
            )
        except RuntimeError:
            # A closed session cannot play a recovery message.
            return

    session.on("error", on_error)
