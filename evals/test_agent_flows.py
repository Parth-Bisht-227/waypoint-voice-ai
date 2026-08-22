import json

import pytest

from livekit.agents import AgentSession, mock_tools
from livekit.plugins import groq

from agent.agent import WayPointAssistant, WaypointSessionState

def function_calls(result) -> list[tuple[str, dict]]:
    """
    Extract tool names and arguments from one AgentSession test turn
    """
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
    return [
        name 
        for name, _ in function_calls(result)
    ]


def mock_prepare_travel_date_change(
        application_id: str,
        new_date: str,
) -> dict:
    """
    Fake backend behavor.

    The LLM still sees and selects the real tool schema, but no
    actual HTTP request or database mutation happens.
    """

    return {
        "status": "confirmation_required",
        "application_id": application_id,
        "current_date": "2026-10-20",
        "proposed_date": new_date,
        "message": "Ask for explicit confirmation before applying.",
    }

def mock_apply_pending_travel_date_change() -> dict:
    return {
        "application_id": "APP001",
        "old_date": "2026-10-20",
        "new_date": "2026-11-20",
        "changed": True,
    }


@pytest.mark.asyncio
async def test_travel_date_requires_explicit_confirmation():
    llm = groq.LLM(
        model = "openai/gpt-oss-20b",
        reasoning_effort="low",
    )

    async with AgentSession[WaypointSessionState](
        llm = llm,
        userdata = WaypointSessionState(),
    ) as session:

        with mock_tools(
            WayPointAssistant,
            {
                "prepare_travel_date_change":
                    mock_prepare_travel_date_change,

                "apply_pending_travel_date_change":
                    mock_apply_pending_travel_date_change,
            },
        ):
            await session.start(
                WayPointAssistant()
            )

            # Turn 1: prepare, but do not mutate
            result1 = await session.run(
                user_input= (
                    "Change APP001 to November 20, 2026."
                )
            )

            names1 = function_names(result1)

            assert "prepare_travel_date_change" in names1
            assert "apply_pending_travel_date_change" not in names1

            prepare_calls = [
                arguments
                for name, arguments in function_calls(result1)
                if name == "prepare_travel_date_change"
            ]

            assert prepare_calls
            assert prepare_calls[0]["application_id"] == "APP001"
            assert prepare_calls[0]["new_date"] == "2026-11-20"

            # Turn 2: positive wording, but NOT explicit authorization.
            result2 = await session.run(
                user_input="That's great."
            )

            names2 = function_names(result2)

            assert "apply_pending_travel_date_change" not in names2

            # Turn 3: explicit authorization.
            result3 = await session.run(
                user_input="Yes, apply it."
            )

            names3 = function_names(result3)

            assert "apply_pending_travel_date_change" in names3


            



