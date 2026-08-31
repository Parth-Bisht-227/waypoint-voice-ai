import pytest
from livekit.agents.llm import ToolError

from agent.agent import WayPointAssistant, WaypointSessionState


class FakeRunContext:
    def __init__(self, userdata: WaypointSessionState) -> None:
        self.userdata = userdata

    def disallow_interruptions(self) -> None:
        raise AssertionError("No mutation should start without a pending change.")


@pytest.mark.asyncio
async def test_apply_requires_a_pending_change() -> None:
    assistant = WayPointAssistant()
    context = FakeRunContext(WaypointSessionState())

    with pytest.raises(ToolError, match="no pending"):
        await assistant.apply_pending_travel_date_change(context)
