import json
import re
from collections.abc import Callable
from datetime import date, timedelta

import pytest

from livekit.agents import APIConnectOptions, AgentSession, mock_tools
from livekit.agents.voice.agent_session import SessionConnectOptions

from agent.agent import WayPointAssistant, WaypointSessionState, create_llm


def function_calls(result) -> list[tuple[str, dict]]:
    """Extract tool names and arguments from one AgentSession test turn."""
    calls = []

    for event in result.events:
        if event.type == "function_call":
            calls.append(
                (
                    event.item.name,
                    json.loads(event.item.arguments),
                )
            )

    return calls


def function_names(result) -> list[str]:
    return [name for name, _ in function_calls(result)]


def function_arguments(result, function_name: str) -> list[dict]:
    """Return arguments for every call to one named function."""
    return [
        arguments
        for name, arguments in function_calls(result)
        if name == function_name
    ]


def assistant_text(result) -> str:
    """Collect assistant message text recorded during one test turn."""
    messages = []

    for event in result.events:
        if event.type != "message" or event.item.role != "assistant":
            continue

        if text := event.item.text_content:
            messages.append(text)

    return "\n".join(messages)


def result_diagnostics(result) -> dict[str, object]:
    """Return useful context when a generative routing assertion fails."""
    return {
        "function_calls": function_calls(result),
        "assistant_text": assistant_text(result),
    }


def future_date(days: int) -> str:
    """Return an ISO date that remains valid as the eval suite ages."""
    return (date.today() + timedelta(days=days)).isoformat()


def mock_get_application_status(_context, application_id: str) -> dict:
    return {
        "application_id": application_id,
        "destination": "Copenhagen",
        "status": "processing",
        "travel_date": future_date(30),
    }


def mock_create_travel_application(
    _context,
    destination: str,
    travel_date: str,
) -> dict:
    return {
        "application_id": "APP005",
        "status": "processing",
    }


def mock_get_missing_documents(_context, application_id: str) -> dict:
    return {
        "application_id": application_id,
        "missing_documents": [],
    }


def mock_prepare_travel_date_change(
    _context,
    application_id: str,
    new_date: str,
) -> dict:
    """
    Return a safe confirmation result without an HTTP request or mutation.

    The LLM still sees and selects the real production tool schema.
    """
    return {
        "status": "confirmation_required",
        "application_id": application_id,
        "current_date": future_date(30),
        "proposed_date": new_date,
    }


def mock_apply_pending_travel_date_change(_context) -> dict:
    return {
        "application_id": "APP001",
        "old_date": future_date(30),
        "new_date": future_date(90),
        "changed": True,
    }


def mock_handoff_to_human(
    _context,
    application_id: str,
    reason_code: str,
) -> dict:
    return {
        "handoff_id": "HANDOFF-TEST-001",
        "application_id": application_id,
        "reason_code": reason_code,
        "status": "requested",
    }


def mock_search_support_knowledge(_context, query: str) -> dict:
    return {
        "answer": (
            "Blocked means the application cannot currently continue through "
            "the normal process. The exact reason must come from "
            "application-specific information or human support."
        ),
    }


def safe_tool_mocks(
    overrides: dict[str, Callable] | None = None,
) -> dict[str, Callable]:
    """Build a fresh complete mock map so no production tool can execute."""
    mocks: dict[str, Callable] = {
        "create_travel_application": mock_create_travel_application,
        "get_application_status": mock_get_application_status,
        "get_missing_documents": mock_get_missing_documents,
        "prepare_travel_date_change": mock_prepare_travel_date_change,
        "apply_pending_travel_date_change": (
            mock_apply_pending_travel_date_change
        ),
        "handoff_to_human": mock_handoff_to_human,
        "search_support_knowledge": mock_search_support_knowledge,
    }

    if overrides:
        mocks.update(overrides)

    return mocks


def provider_llm():
    return create_llm()


def eval_session_connect_options() -> SessionConnectOptions:
    return SessionConnectOptions(
        llm_conn_options=APIConnectOptions(
            max_retry=0,
            retry_interval=0.5,
            timeout=12.0,
        )
    )


async def run_single_turn(
    user_input: str,
    *,
    tool_overrides: dict[str, Callable] | None = None,
):
    """Run one provider-backed turn in a new session with all tools mocked."""
    async with AgentSession[WaypointSessionState](
        llm=provider_llm(),
        userdata=WaypointSessionState(),
        conn_options=eval_session_connect_options(),
    ) as session:
        with mock_tools(
            WayPointAssistant,
            safe_tool_mocks(tool_overrides),
        ):
            await session.start(WayPointAssistant())
            return await session.run(user_input=user_input)


@pytest.mark.asyncio
async def test_travel_date_prepares_before_natural_confirmation():
    requested_date = date.today() + timedelta(days=90)
    spoken_date = (
        f"{requested_date:%B} "
        f"{requested_date.day}, {requested_date.year}"
    )
    expected_date = requested_date.isoformat()

    async with AgentSession[WaypointSessionState](
        llm=provider_llm(),
        userdata=WaypointSessionState(),
        conn_options=eval_session_connect_options(),
    ) as session:
        with mock_tools(
            WayPointAssistant,
            safe_tool_mocks(),
        ):
            await session.start(WayPointAssistant())

            # Turn 1: prepare, but do not mutate.
            result1 = await session.run(
                user_input=f"Change APP001 to {spoken_date}."
            )

            names1 = function_names(result1)
            diagnostics1 = result_diagnostics(result1)

            assert "prepare_travel_date_change" in names1, diagnostics1
            assert (
                "apply_pending_travel_date_change" not in names1
            ), diagnostics1

            prepare_calls = function_arguments(
                result1,
                "prepare_travel_date_change",
            )

            assert prepare_calls, diagnostics1
            assert (
                prepare_calls[0]["application_id"] == "APP001"
            ), diagnostics1
            assert prepare_calls[0]["new_date"] == expected_date, diagnostics1

            # Turn 2: a later natural, action-bearing confirmation may apply.
            result2 = await session.run(
                user_input="Yeah, that's perfect."
            )

            names2 = function_names(result2)
            diagnostics2 = result_diagnostics(result2)

            assert "apply_pending_travel_date_change" in names2, diagnostics2
            assert "prepare_travel_date_change" not in names2, diagnostics2


@pytest.mark.asyncio
async def test_new_application_requires_confirmation_before_creation():
    requested_date = date.today() + timedelta(days=120)
    spoken_date = (
        f"{requested_date:%B} "
        f"{requested_date.day}, {requested_date.year}"
    )
    expected_date = requested_date.isoformat()

    async with AgentSession[WaypointSessionState](
        llm=provider_llm(),
        userdata=WaypointSessionState(),
        conn_options=eval_session_connect_options(),
    ) as session:
        with mock_tools(
            WayPointAssistant,
            safe_tool_mocks(),
        ):
            await session.start(WayPointAssistant())

            proposal = await session.run(
                user_input=(
                    "Create a new Waypoint application for Japan with a "
                    f"travel date of {spoken_date}."
                )
            )
            proposal_names = function_names(proposal)
            proposal_diagnostics = result_diagnostics(proposal)

            assert "create_travel_application" not in proposal_names, (
                proposal_diagnostics
            )

            confirmation = await session.run(
                user_input="Yes, create it."
            )
            confirmation_names = function_names(confirmation)
            confirmation_diagnostics = result_diagnostics(confirmation)

            assert confirmation_names.count(
                "create_travel_application"
            ) == 1, confirmation_diagnostics

            calls = function_arguments(
                confirmation,
                "create_travel_application",
            )
            assert calls[0] == {
                "destination": "Japan",
                "travel_date": expected_date,
            }, confirmation_diagnostics


@pytest.mark.asyncio
async def test_current_application_status_routes_to_application_tool():
    result = await run_single_turn("What is the status of APP001?")
    names = function_names(result)

    assert "get_application_status" in names, names
    assert "search_support_knowledge" not in names, names
    assert "handoff_to_human" not in names, names

    status_calls = function_arguments(result, "get_application_status")
    assert status_calls, function_calls(result)
    assert status_calls[0]["application_id"] == "APP001", status_calls


@pytest.mark.asyncio
async def test_general_knowledge_routes_to_knowledge_tool():
    result = await run_single_turn("What does blocked mean?")
    names = function_names(result)

    assert "search_support_knowledge" in names, names
    assert "get_application_status" not in names, names


@pytest.mark.asyncio
async def test_explicit_human_handoff_uses_user_request_reason():
    result = await run_single_turn(
        "I want to speak to a human about APP001."
    )
    names = function_names(result)

    assert "handoff_to_human" in names, names

    handoff_calls = function_arguments(result, "handoff_to_human")
    assert handoff_calls, function_calls(result)
    assert handoff_calls[0]["application_id"] == "APP001", handoff_calls
    assert handoff_calls[0]["reason_code"] == "user_request", handoff_calls


@pytest.mark.asyncio
async def test_confusion_does_not_trigger_accidental_handoff():
    result = await run_single_turn("I'm confused about APP004's status.")
    names = function_names(result)

    assert "get_application_status" in names, names
    assert "handoff_to_human" not in names, names

    status_calls = function_arguments(result, "get_application_status")
    assert status_calls, function_calls(result)
    assert status_calls[0]["application_id"] == "APP004", status_calls


@pytest.mark.asyncio
async def test_incomplete_date_request_asks_for_detail_without_handoff():
    result = await run_single_turn("Could you change the travel date to")
    names = function_names(result)

    assert "handoff_to_human" not in names, names
    assert "prepare_travel_date_change" not in names, names
    assert "apply_pending_travel_date_change" not in names, names

    response = assistant_text(result).lower()
    assert response, response
    assert any(
        marker in response
        for marker in (
            "what date",
            "which date",
            "new date",
            "travel date",
            "date would",
        )
    ), response


def mock_unsupported_knowledge(_context, query: str) -> dict:
    return {"found": False}


@pytest.mark.asyncio
async def test_unsupported_knowledge_does_not_invent_an_allowance():
    result = await run_single_turn(
        "What is the baggage allowance on Nordic Airlines?",
        tool_overrides={
            "search_support_knowledge": mock_unsupported_knowledge,
        },
    )
    names = function_names(result)
    response = assistant_text(result).lower()

    assert "search_support_knowledge" in names, names
    assert response, response
    assert any(
        marker in response
        for marker in (
            "grounded",
            "don't have",
            "don’t have",
            "do not have",
            "no information",
            "not available",
            "unavailable",
            "can't find",
            "cannot find",
            "couldn't find",
            "could not find",
            "not finding",
        )
    ), response

    numeric_allowance = re.compile(
        r"\b\d+(?:\.\d+)?\s*"
        r"(?:(?:checked|carry[- ]on|cabin)\s+)?"
        r"(?:kg|kgs|kilograms?|lb|lbs|pounds?|bags?|pieces?)\b"
    )
    assert numeric_allowance.search(response) is None, response
