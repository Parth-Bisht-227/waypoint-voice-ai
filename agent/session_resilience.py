"""Small helpers for latency fillers and terminal LLM failures."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Sequence

from livekit.agents import AgentSession, ErrorEvent
from livekit.agents.llm import LLMError


LATENCY_FILLER_DELAY_SECONDS = 2.0

LATENCY_FILLERS = (
    "One moment.",
    "Just a second.",
    "Give me a moment.",
    "I'm working on that.",
    "Let me check that.",
    "Let me look into that.",
)

LLM_FAILURE_MESSAGES = (
    "I'm having trouble responding. Could you say that once more?",
    "Sorry, I hit a brief connection issue. Could you repeat that?",
    "I couldn't complete that response. Please say it once more.",
)


def schedule_latency_filler(
    session: AgentSession,
    phrases: Sequence[str] = LATENCY_FILLERS,
    *,
    delay: float = LATENCY_FILLER_DELAY_SECONDS,
) -> asyncio.Task[None]:
    """Speak once if the agent is still thinking after the delay."""

    async def speak_if_still_waiting() -> None:
        await asyncio.sleep(delay)
        if session.agent_state != "thinking" or session.user_state == "speaking":
            return

        try:
            session.say(
                random.choice(tuple(phrases)),
                allow_interruptions=True,
                add_to_chat_ctx=False,
            )
        except RuntimeError:
            # The session may have closed while the delay was running.
            return

    return asyncio.create_task(speak_if_still_waiting())


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
