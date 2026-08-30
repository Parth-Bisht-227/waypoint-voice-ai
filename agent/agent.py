import asyncio
import sys
from dataclasses import dataclass
from uuid import uuid4
from typing import Literal
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    Agent, 
    AgentServer,
    AgentSession,
    APIConnectOptions,
    RunContext,
    TurnHandlingOptions,
    function_tool,
    inference,
    utils,
)
from livekit.agents.voice.agent_session import SessionConnectOptions
from agent.prompts import build_waypoint_instructions
from agent.session_resilience import (
    LATENCY_FILLERS,
    attach_llm_failure_handler,
    schedule_latency_filler,
)
from agent.retriever import search_faq_answer
from agent.application_signals import (
    ApplicationSignalSender,
    make_application_signal_sender,
    publish_application_signal,
)
from observability.session_observer import (
    attach_session_observers,
    save_session_report,
)

from livekit.plugins import (
    cartesia,
    deepgram,
    groq,
    silero,
)

from livekit.agents.llm import ChatMessage, ToolError

import os
import re


for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


ENV_PATH = Path(__file__).resolve().parent / ".env.local"
load_dotenv(ENV_PATH)

BACKEND_BASE_URL = os.getenv(
    "BACKEND_BASE_URL",
    "http://127.0.0.1:8000"
)

# helper fn, needed to ensure that stt mmisheard application id is not passed directly to the agent
def normalize_application_id(value:str) -> str | None:
    normalized = value.lower().strip()

    replacements = {
        "double zero" : "00",
        "zero": "0",
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
    }


    for spoken, digit in replacements.items():
        normalized = normalized.replace(spoken, digit)

    # logic hardcoded as per our current APP ID format for now

    # Keep only digits
    digits = "".join(re.findall(r"\d", normalized))

    # Groq/STT sometimes gives "0001" instead of "001"
    if len(digits) == 4 and digits.startswith("0"):
        digits = digits[-3:]

    if len(digits) != 3:
        return None

    return f"APP{digits}"


@dataclass
class WaypointSessionState:
    pending_application_id: str | None = None
    pending_travel_date: str | None = None
    pending_idempotency_key: str | None = None
    application_signal_sender: ApplicationSignalSender | None = None

    # the state exists only during the call


class WayPointAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=build_waypoint_instructions()
        )
        self._latency_filler_task: asyncio.Task[None] | None = None

    async def on_user_turn_completed(
        self,
        turn_ctx,
        new_message: ChatMessage,
    ) -> None:
        if self._latency_filler_task and not self._latency_filler_task.done():
            self._latency_filler_task.cancel()

        self._latency_filler_task = schedule_latency_filler(
            self.session,
            LATENCY_FILLERS,
        )

    async def on_exit(self) -> None:
        if self._latency_filler_task and not self._latency_filler_task.done():
            self._latency_filler_task.cancel()
            await asyncio.gather(
                self._latency_filler_task,
                return_exceptions=True,
            )

    @function_tool()
    async def get_application_status(
        self, 
        context: RunContext[WaypointSessionState],
        application_id: str,
    ) -> dict:
        """
        Look up the current status and basic details of a travel application.

        Args:
            application_id : The application identifier, for example APP001.
        """

        canonical_id = normalize_application_id(application_id)

        if canonical_id is None:
            raise ToolError(
                "I could not confidently understand the application ID. "
                "Ask the user to repeat or spell it."
            )

        url = (
            f"{BACKEND_BASE_URL}"
            f"/applications/{canonical_id}"
        )

        session = utils.http_context.http_session()

        '''
        http_session() = “give me the shared HTTP client I can use to call my backend.”
        And then:
            async with session.get(url) as response:
        actually sends the GET request.
        '''

        async with session.get(
            url,
            timeout = 3,
        ) as response:

            if response.status == 404:
                raise ToolError(
                    f"Application {canonical_id} was not found."
                )
            if response.status != 200:
                raise ToolError(
                    "The application service is temporarily unavailable."
                )

            data = await response.json()

            result = {
                "application_id": data["application_id"],
                "destination": data["destination"],
                "status": data["status"],
                "travel_date": data["travel_date"],
            }

        await publish_application_signal(
            context.userdata.application_signal_sender,
            "application_context",
            canonical_id,
        )
        return result


    @function_tool()
    async def get_missing_documents(
        self,
        context: RunContext[WaypointSessionState],
        application_id: str,
    ) -> dict:
        """
        Look up which documents are currently missing from an application.

        Args:
            application_id: The application identifier, for example APP001.
        """

        canonical_id = normalize_application_id(application_id)
        if canonical_id is None:
            raise ToolError(
                "I could not confidently understand the application ID. "
                "Ask the user to repeat it."
            )

        url = (
            f"{BACKEND_BASE_URL}"
            f"/applications/{canonical_id}/missing-documents"
        )

        session = utils.http_context.http_session()

        async with session.get(url, timeout=3) as response:

            if response.status == 404:
                raise ToolError(
                    f"Application {canonical_id} was not found."
                )

            if response.status != 200:
                raise ToolError(
                    "The application service is temporarily unavailable. "
                )

            data = await response.json()

            result = {
                "application_id": data["application_id"],
                "missing_documents": data["missing_documents"],
            }

        await publish_application_signal(
            context.userdata.application_signal_sender,
            "application_context",
            canonical_id,
        )
        return result

    @function_tool()
    async def prepare_travel_date_change(
        self, 
        context: RunContext[WaypointSessionState],
        application_id: str,
        new_date: str,
    ) -> dict:
        """
        Prepare a future travel-date change without applying it.

        Args:
            application_id: Application identifier.
            new_date: Desired travel date in YYYY-MM-DD format.
        
        """

        canonical_id = normalize_application_id(application_id)

        if canonical_id is None:
            raise ToolError("I could not confidently understand the application ID.")

        try:
            parsed_date = date.fromisoformat(new_date)
        except ValueError:
            raise ToolError(
                "I could not understand the requested travel date."
            )

        if parsed_date <= date.today():
            raise ToolError(
                f"The parsed travel date {parsed_date.isoformat()} is not in the future. "
                "Ask the user to repeat the date including the year."
            )

        canonical_date = parsed_date.isoformat()

        # Verify application exists, but don't mutate anything...
        session = utils.http_context.http_session()

        url = f"{BACKEND_BASE_URL}/applications/{canonical_id}"

        async with session.get(url, timeout=3) as response:

            if response.status == 404:
                raise ToolError(
                    f"Application {canonical_id} was not found."
                )

            if response.status != 200:
                raise ToolError(
                    "The application service is temporarily unavailable."
                )

            application = await response.json()

        state = context.userdata

        state.pending_application_id = canonical_id
        state.pending_travel_date = canonical_date
        state.pending_idempotency_key = f"date-{uuid4().hex}"

        result = {
            "status": "confirmation_required",
            "application_id": canonical_id,
            "current_date": application["travel_date"],
            "proposed_date": canonical_date,
        }

        await publish_application_signal(
            state.application_signal_sender,
            "application_context",
            canonical_id,
        )
        return result


    @function_tool()
    async def apply_pending_travel_date_change(
        self,
        context: RunContext[WaypointSessionState],
    ) -> dict:
        """Apply the prepared travel-date change after caller confirmation."""

        state = context.userdata

        if(
            state.pending_application_id is None 
            or state.pending_travel_date is None
            or state.pending_idempotency_key is None
        ):
            raise ToolError(
                "There is no pending travel-date change to apply."
            )


        application_id  = state.pending_application_id
        new_date = state.pending_travel_date
        idempotency_key = state.pending_idempotency_key

        # A durable external mutation is about to begin.
        context.disallow_interruptions()

        url = (
            f"{BACKEND_BASE_URL}"
            f"/applications/{application_id}/travel-date"
        )

        session = utils.http_context.http_session()

        try:
            async with session.patch(
                url,
                json={
                    "new_date": new_date,
                    "idempotency_key": idempotency_key,
                },
                timeout=3,
            ) as response:

                if response.status == 400:
                    raise ToolError(
                        "The requested travel date is not valid."
                    )

                if response.status == 404:
                    raise ToolError(
                        f"Application {application_id} was not found."
                    )

                if response.status == 409:
                    raise ToolError(
                        "The date-change request conflicts with "
                        "an earlier request."
                    )

                if response.status != 200:
                    raise ToolError(
                        "I could not safely complete the date change."
                    )

                result = await response.json()

        except TimeoutError:
            # IMPORTANT: do NOT clear pending state.
            # A retry will reuse the same idempotency key.
            raise ToolError(
                "The date-change request timed out. "
                "Do not claim that the change succeeded."
            )

        # Only clear the pending mutation after confirmed backend success.
        state.pending_application_id = None
        state.pending_travel_date = None
        state.pending_idempotency_key = None

        await publish_application_signal(
            state.application_signal_sender,
            "application_updated",
            application_id,
        )

        return result


    @function_tool()
    async def handoff_to_human(
        self,
        context: RunContext[WaypointSessionState],
        application_id: str,
        reason_code: Literal["user_request"],
    ) -> dict:
        """
        Request human support for an application.

        Call only when the caller clearly asks to speak with a person.

        Args:
            application_id: Application identifier.
            reason_code: Use user_request for an explicit user request.
        
        """

        canonical_id = normalize_application_id(application_id)

        if canonical_id is None:
            raise ToolError(
                "I could not confidently understand the application ID. "
                "Ask the user to repeat it."
            )

        url = (
            f"{BACKEND_BASE_URL}"
            F"/applications/{canonical_id}/handoffs"
        )

        session = utils.http_context.http_session()

        #  A real external state-changing operation is about to happen
        context.disallow_interruptions()

        async with session.post(
            url,
            json={
                "reason_code": reason_code,
            },
            timeout = 3,
        ) as response:
            if response.status == 404:
                raise ToolError(
                    f"Application {canonical_id} was not found."
                )
            
            if response.status == 422:
                raise ToolError(
                    "The handoff reason was not valid."
                )

            if response.status != 201:
                raise ToolError(
                    "Human support could not be requested safely."
                )

            data = await response.json()

        return {
            "handoff_id": data["handoff_id"],
            "application_id": data["application_id"],
            "reason_code": data["reason_code"],
            "status": data["status"],
        }
            
    @function_tool()
    async def search_support_knowledge(
        self,
        context: RunContext[WaypointSessionState],
        query: str,
    ) -> dict:
        """
        Search grounded Waypoint support or curated Japan visa guidance.

        Args:
            query: A concise question; include Japan for Japan visa follow-ups.
        
        """
        return search_faq_answer(query)

    '''The LLM receives one compact answer from the locally cached FAQ search.'''


server = AgentServer() 
# This is the process that waits for LiveKit to assign realtime agent sessions/jobs.
# currently it runs locally on the system


# This registers the function as the named realtime session handler.
@server.rtc_session(
    agent_name="waypoint-agent",
    on_session_end=save_session_report,
)
async def waypoint_agent(ctx: agents.JobContext):

    # this represents one realtime conversation
    session_state = WaypointSessionState(
        application_signal_sender=make_application_signal_sender(ctx),
    )
    session = AgentSession[WaypointSessionState](

        userdata = session_state, # lk exposes this session userdata through RunContext, specifically for temporary
        # workflow/session state like this
        # this means that this conversation's "userdata" has the shape of "WaypointSessionState"

        vad = silero.VAD.load(), 

        stt= deepgram.STT(
            model = "nova-3",
            language="en",
        ),
        
        llm=groq.LLM(
                model="openai/gpt-oss-20b",
                reasoning_effort="low",
        ),

        tts = cartesia.TTS(
            model = "sonic-3.5",
            voice = "47c38ca4-5f35-497b-b1a3-415245fb35e1",
            language= "en",
        ),

        turn_handling = TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
            endpointing={
                "mode": "fixed",
                "min_delay": 0.6,
                "max_delay": 2.5,
            },
            preemptive_generation={"enabled": False},
        ),
        conn_options=SessionConnectOptions(
            llm_conn_options=APIConnectOptions(
                max_retry=2,
                retry_interval=5.0,
                timeout=6.0,
            ),
        ),
    )

    attach_session_observers(session)
    attach_llm_failure_handler(session)

    # vad asks --> is the user currently producing speech like audio?
    # detects the speech and silence in btw, but it does not necessarily understand whether we've finished
    # our thought or not

    # turn detector on the other hand, helps ans "has the user actually completed their conversational turn?"

    await session.start(
        room = ctx.room,
        agent= WayPointAssistant(),
    )

    await session.generate_reply(
        instructions=(
            "Greet the user briefly and ask how you can help with their travel."
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
