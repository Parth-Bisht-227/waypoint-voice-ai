from dataclasses import dataclass
from uuid import uuid4
from typing import Literal
from datetime import date
from pathlib import Path
from textwrap import dedent
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    Agent, 
    AgentServer,
    AgentSession,
    ConversationItemAddedEvent,
    RunContext,
    TurnHandlingOptions,
    function_tool,
    inference,
    utils,
)
from agent.retriever import search_faqs
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
    pending_confirmation_granted: bool = False
    latest_final_user_text: str | None = None
    application_signal_sender: ApplicationSignalSender | None = None

    # the state exists only during the call


_CONFIRMATION_VETO_PATTERN = re.compile(
    r"\b(?:no|nope|not|wait|stop|actually|instead|but|wrong)\b"
    r"|\bcancel(?:led)?\b"
    r"|\bhold (?:on|up)\b"
    r"|\bnever ?mind\b"
    r"|\bforget it\b"
)
_DATE_LIKE_PATTERN = re.compile(
    r"\d"
    r"|\b(?:"
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december|"
    r"today|tomorrow|yesterday"
    r")\b"
)
_CONFIRMATION_WORDS = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "please",
        "confirm",
        "confirmed",
        "i",
        "it",
        "this",
        "that",
        "is",
        "the",
        "date",
        "change",
        "apply",
        "go",
        "ahead",
        "and",
        "correct",
        "right",
        "sound",
        "sounds",
        "good",
        "do",
        "proceed",
        "now",
    }
)
_CONFIRMATION_MARKERS = frozenset(
    {"yes", "yeah", "yep", "confirm", "confirmed", "correct"}
)
_CONFIRMATION_ACTIONS = (
    "change it",
    "apply it",
    "go ahead",
    "do it",
    "i confirm",
    "confirm it",
    "proceed",
)


def is_explicit_confirmation(text: str | None) -> bool:
    """Classify a short, complete confirmation with deterministic safeguards."""

    if not text:
        return False

    normalized = text.casefold().replace("’", "'")
    normalized = re.sub(r"\bdon'?t\b", "do not", normalized)
    normalized = re.sub(r"\bthat'?s\b", "that is", normalized)
    normalized = re.sub(r"\bit'?s\b", "it is", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = " ".join(normalized.split())

    if (
        not normalized
        or "?" in text
        or _CONFIRMATION_VETO_PATTERN.search(normalized)
        or _DATE_LIKE_PATTERN.search(normalized)
    ):
        return False

    words = normalized.split()
    if len(words) > 12 or not set(words).issubset(_CONFIRMATION_WORDS):
        return False

    return bool(
        _CONFIRMATION_MARKERS.intersection(words)
        or any(action in normalized for action in _CONFIRMATION_ACTIONS)
    )


_HANDOFF_TARGET = (
    r"(?:human|person|representative|live agent|support agent|"
    r"customer service|agent)"
)
_NEGATED_HANDOFF_PATTERN = re.compile(
    r"\b(?:do not|never) "
    r"(?:want|need|speak|talk|connect|transfer|get|put|hand off|handoff)\b"
    r"|\bcannot (?:speak|talk|connect|transfer|get|reach)\b"
    r"|\b(?:want|need|would like) to not "
    r"(?:speak|talk|connect|transfer|get|be transferred)\b"
    rf"|\bnot (?:asking|requesting) (?:for )?(?:a |an |the )?"
    rf"{_HANDOFF_TARGET}\b"
    rf"|\b(?:no|not) (?:a |an |the )?{_HANDOFF_TARGET}\b"
)
_DEFERRED_HANDOFF_PATTERN = re.compile(
    r"\b(?:maybe later|not yet|not now)\b"
)
_HANDOFF_INFORMATION_PATTERN = re.compile(
    r"^(?:what|who|why|how)\b"
    r"|^(?:do|should|would) i\b"
    r"|^do you have\b"
    r"|^(?:can|could|would) you (?:tell|explain)\b"
    r"|\bi (?:want|need|would like) to "
    r"(?:know|understand|learn|ask|find out)\b"
)
_HANDOFF_TARGET_PATTERN = re.compile(
    rf"\b{_HANDOFF_TARGET}\b"
)
_HANDOFF_INTENT_PATTERN = re.compile(
    r"\b(?:speak|talk) (?:to|with)\b"
    r"|\b(?:connect|transfer|get|put) me\b"
    r"|\bhand (?:me )?off\b|\bhandoff me\b"
)
_DIRECT_HANDOFF_DESIRE_PATTERN = re.compile(
    rf"\bi (?:want|need|would like) "
    rf"(?:to (?:speak|talk) (?:to|with) )?"
    rf"(?:a |an |the )?{_HANDOFF_TARGET}\b"
)
_DIRECT_HANDOFF_REQUESTS = frozenset(
    {
        "human",
        "human please",
        "person please",
        "representative please",
        "agent please",
        "live agent",
        "live agent please",
        "support agent please",
        "customer service please",
        "human support please",
        "to a human",
        "to a person",
        "to a representative",
        "to an agent",
    }
)


def is_explicit_handoff_request(text: str | None) -> bool:
    """Return whether a finalized user turn explicitly requests a person."""

    if not text:
        return False

    normalized = text.casefold().replace("’", "'")
    normalized = re.sub(r"\bdon'?t\b", "do not", normalized)
    normalized = re.sub(r"\bcan'?t\b", "cannot", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = " ".join(normalized.split())

    if (
        not normalized
        or len(normalized.split()) > 30
        or _NEGATED_HANDOFF_PATTERN.search(normalized)
        or _DEFERRED_HANDOFF_PATTERN.search(normalized)
        or _HANDOFF_INFORMATION_PATTERN.search(normalized)
    ):
        return False

    if normalized in _DIRECT_HANDOFF_REQUESTS:
        return True

    if _DIRECT_HANDOFF_DESIRE_PATTERN.search(normalized):
        return True

    return bool(
        _HANDOFF_TARGET_PATTERN.search(normalized)
        and _HANDOFF_INTENT_PATTERN.search(normalized)
    )


def attach_confirmation_tracking(
    session: AgentSession[WaypointSessionState],
) -> None:
    """Track whether a pending change was confirmed in a later user turn."""

    def on_conversation_item_added(event: ConversationItemAddedEvent) -> None:
        item = event.item
        if not isinstance(item, ChatMessage) or item.role != "user":
            return

        state = session.userdata
        state.latest_final_user_text = item.text_content
        if state.pending_application_id is None:
            state.pending_confirmation_granted = False
            return

        state.pending_confirmation_granted = is_explicit_confirmation(
            item.text_content
        )

    session.on("conversation_item_added", on_conversation_item_added)


class WayPointAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=dedent(
                f"""
                You are Waypoint, a helpful travel-support voice assistant.

                ## Identity and voice style
                - Speak naturally and briefly. Default to one short sentence;
                  use at most two only when necessary.
                - Do not repeat information, explain internal tools, or narrate
                  policy and workflow. Use plain speech, without Markdown or emojis.
                - Use the canonical application_id returned by the latest tool.
                  Speak APP004 as "A P P zero zero four." Never echo a malformed ID.

                ## Grounding and application tools
                - Use the relevant application tool for every current application
                  fact or action; do not rely on remembered status or dates.
                - Never invent application facts, missing documents, successful
                  updates, handoff state, policies, or unsupported actions.
                - Do not imply a missing document automatically caused a blocked
                  status. Do not offer uploads, bookings, cancellations, or reviews.
                - If an ID is unclear or a tool fails, ask or explain briefly and
                  never claim success.

                ## Travel-date changes
                Today's date is {date.today().isoformat()}.
                - Require an application ID and a complete future date with a year.
                  Ask only for information that is missing; never guess the year.
                - A month, day, and four-digit year is a complete date. When all
                  three are present, do not ask the user to repeat the year.
                - Preparation is non-mutating validation and needs no consent.
                  Once the ID and complete date are known, the next action must be
                  prepare_travel_date_change. Do not speak or ask for confirmation
                  before calling it.
                - After it returns confirmation_required, ask exactly one short
                  confirmation using its canonical application_id and proposed_date.
                  Phrase it as a proposed action, for example, "Change A P P
                  zero zero four to December fifteenth, twenty twenty-seven?"
                  Do not say the date "is set" or otherwise imply it changed.
                - On a later clear confirmation such as "yes", "yeah", "confirmed",
                  "please change it", or "go ahead", call
                  apply_pending_travel_date_change immediately. Do not ask again or
                  require the ID or date to be repeated.
                - A correction requires prepare_travel_date_change again, followed
                  by one new confirmation. Vague remarks such as "okay" or
                  "that's great" do not authorize a change.
                - Claim success only from a successful apply result.

                ## Human handoff
                - Call handoff_to_human only when the user's latest completed
                  turn explicitly asks to speak to a human; use reason_code
                  "user_request".
                - Never create a handoff because an ID or date is missing, the
                  user corrects themselves, seems confused, or clarification is
                  needed. Ask one brief clarifying question instead.
                - For unsupported requests or failures, explain briefly. You may
                  tell the user they can explicitly ask for a human, but do not
                  create a handoff unless they do so.
                - Do not claim a handoff until the tool succeeds.
                - After success, say only that a human-support request was created.
                  Do not promise a notification, response time, or contact outcome.

                ## Knowledge questions
                - For general Waypoint policy, capability, or explanation, call
                  search_support_knowledge and answer only from its results.
                - If nothing relevant is found, say grounded information is
                  unavailable. Use application tools for current application state.
                """
            ).strip()
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
        Mandatory non-mutating validation for a requested travel-date change.

        Calling this tool does not update the backend and needs no user consent.
        Once the application ID and complete requested date are known, call it
        as the next action without speaking first. A month, day, and four-digit
        year is complete and must not be requested again. If the user corrects
        the date, call this tool again with the corrected date.

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
        state.pending_confirmation_granted = False

        result = {
            "status": "confirmation_required",
            "application_id": canonical_id,
            "current_date": application["travel_date"],
            "proposed_date": canonical_date,
            "message": (
                "Ask the user to explicitly confirm this exact date "
                "before applying the change."
            ),
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
        """
        Apply the currently pending travel-date change.

        Call this immediately after a later user turn clearly confirms the
        prepared proposal. Do not ask the user to restate the ID or date.
        The deterministic Python gate refuses an unconfirmed application.
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

        if not state.pending_confirmation_granted:
            raise ToolError(
                "The pending travel-date change has not been explicitly "
                "confirmed in a later user turn. Ask the user to confirm it."
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
        state.pending_confirmation_granted = False

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

        Call this only when the user's latest completed turn explicitly asks
        to speak to a human. Missing information, corrections, confusion,
        unsupported requests, and clarification attempts must not create a
        handoff automatically.

        Args:
            application_id: Application identifier.
            reason_code: Use user_request for an explicit user request.
        
        """

        state = context.userdata
        if not is_explicit_handoff_request(state.latest_final_user_text):
            raise ToolError(
                "The user has not explicitly requested a human. Continue "
                "helping and ask only for any missing application or date "
                "details."
            )

        if reason_code != "user_request":
            raise ToolError(
                "An explicit human request must use reason_code user_request."
            )

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
        Search Waypoint's grounded support knowledge.

        Use this for general support, policy, capability, and explanatory
        questions that are not specific to the current state of an application.

        Args:
            query: The user's support question or a concise search query.
        
        """
        results = search_faqs(
            query = query,
            top_k = 3,
            min_score = 2,
        )
        if not results:
            return {
                "found": False,
                "results": [],
            }

        return {
            "found": True,
            "results": results,
        }

    ''' path here is simply: LLM -> Py fn tool -> search_faqs() -> faqs.json cached in memory
    -> top matches returned'''



        


   








server = AgentServer() 
# This is the process that waits for LiveKit to assign realtime agent sessions/jobs.
# currently it runs locally on the system...

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
    )

    attach_confirmation_tracking(session)
    attach_session_observers(session)

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
