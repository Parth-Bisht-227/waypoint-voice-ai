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
    RunContext,
    TurnHandlingOptions,
    function_tool,
    inference,
    utils,
)

from livekit.plugins import (
    cartesia,
    deepgram,
    groq,
    silero,
)

from livekit.agents.llm import ToolError

import os
import re


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

    # the state exists only during the call

class WayPointAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=
            
            f"""
                You are Waypoint, a helpful travel-support voice assistant.

                Keep responses short, natural, and conversational. Most spoken responses should be one or two sentences.
                Use plain punctuation in spoken responses. Do not use emojis or Markdown formatting.

                ## Grounding and tools

                For application-specific information, always use the available tools.

                Never invent or assume:

                * application status;
                * travel dates;
                * missing documents;
                * successful updates;
                * handoff state;
                * policies or actions not supported by a tool or grounded knowledge.

                Only state facts returned by tools or grounded knowledge.
                
                Do not use emojis or Markdown formatting in spoken responses.
                Do not infer that a missing document will automatically resolve a blocked application.
                Do not offer uploads, reviews, itinerary printing, bookings, cancellations, or other actions unless an available tool explicitly supports them.

                When application information is requested, use the relevant tool rather than relying on conversation memory.
                If an application cannot be found or an ID is unclear, ask the user to repeat or clarify it.

                ## Travel-date changes
                Today's date is {date.today().isoformat()}.
                                For travel-date changes, never invent or guess the year.
                                If the user gives a month and day without a clear year,
                                ask which year they mean before preparing the change.

                When the user asks to change a travel date:

                1. Collect the application ID and requested date.
                2. Call `prepare_travel_date_change`.
                3. Tell the user the exact application and proposed date and ask for explicit confirmation.
                4. Do not claim that anything has changed yet.
                5. If the user corrects the date before confirmation, call `prepare_travel_date_change` again with the corrected date.
                6. Call `apply_pending_travel_date_change` only after a clear confirmation such as:

                * "yes"
                * "confirm"
                * "apply it"
                * "go ahead"
                * "yes, change it"
                7. Do not treat vague or incomplete statements such as "okay", "that's great", partial speech, or unrelated statements as confirmation.
                8. Never say the date was updated until `apply_pending_travel_date_change` returns a successful backend result.

                If a tool fails or times out, explain the failure briefly and do not pretend the requested action succeeded.

                Human Handoff:

                - If the user explicitly asks to speak to a human, use handoff_to_human
                with reason_code "user_request".

                - Use human handoff when the request cannot be safely resolved because of:
                unsupported functionality,
                repeated failed clarification,
                critical backend failure,
                conflicting state,
                or persistent uncertainty about a critical identifier.

                - Do not hand off merely because a question is difficult.

                - Do not claim that human support has been requested until
                handoff_to_human returns successfully.

                - Keep the spoken acknowledgement short after a successful handoff.

            """
        )

    @function_tool()
    async def get_application_status(
        self, 
        context: RunContext,
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

            return {
                "application_id": data["application_id"],
                "destination": data["destination"],
                "status": data["status"],
                "travel_date": data["travel_date"],
            }


    @function_tool()
    async def get_missing_documents(
        self,
        context: RunContext,
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

            return{
                "application_id": data["application_id"],
                "missing_documents": data["missing_documents"],
            }

    @function_tool()
    async def prepare_travel_date_change(
        self, 
        context: RunContext[WaypointSessionState],
        application_id: str,
        new_date: str,
    ) -> dict:
        """
        Prepare a travel-date change without modifying the application.

        Use this when the user asks to change their travel date.
        If the user corrects the date, call this again with the corrected date.

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

        return {
            "status": "confirmation_required",
            "application_id": canonical_id,
            "current_date": application["travel_date"],
            "proposed_date": canonical_date,
            "message": (
                "Ask the user to explicitly confirm this exact date "
                "before applying the change."
            ),
        }


    @function_tool()
    async def apply_pending_travel_date_change(
        self,
        context: RunContext[WaypointSessionState],
    ) -> dict:
        """
            Apply the currently pending travel-date change.

            Call this only after the user explicitly confirms the exact
            application and travel date previously proposed.
        """

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

        return result


    @function_tool()
    async def handoff_to_human(
        self,
        context: RunContext[WaypointSessionState],
        application_id: str,
        reason_code: Literal[
            "user_request",
            "unsupported_request",
            "repeated_clarification_failure",
            "backend_failure",
            "state_conflict",
            "critical_entity_uncertain",
        ]
    ) -> dict:
        """
        Request human support for an application.

        Use this when:
        - the user explicitly asks for a human;
        - the request is unsupported and needs human assistance;
        - repeated clarification attempts have failed;
        - a critical backend failure prevents safe resolution;
        - application state is conflicting;
        - an important spoken entity cannot be understood reliably.

        Args:
            application_id: Application identifier.
            reason_code: Deterministic reason for the handoff.
        
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
            


        


   








server = AgentServer() 
# This is the process that waits for LiveKit to assign realtime agent sessions/jobs.
# currently it runs locally on the system...

@server.rtc_session(agent_name="waypoint-agent") # this registers the fn as handler for realtime sessions for the named agent...
async def waypoint_agent(ctx: agents.JobContext):

    # this represents one realtime conversation
    session = AgentSession[WaypointSessionState](

        userdata = WaypointSessionState(), # lk exposes this session userdata through RunContext, specifically for temporary
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
        ),
    )
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