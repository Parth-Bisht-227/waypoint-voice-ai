import pytest
from livekit.agents.llm import ToolError

from agent.agent import WayPointAssistant, WaypointSessionState
from agent.prompts import build_waypoint_instructions


class RecordingTTS:
    def __init__(self) -> None:
        self.languages: list[str] = []

    def update_options(self, *, language: str) -> None:
        self.languages.append(language)


class FakeSession:
    def __init__(self, tts: object) -> None:
        self.tts = tts


class FakeRunContext:
    def __init__(self, state: WaypointSessionState, tts: object) -> None:
        self.userdata = state
        self.session = FakeSession(tts)


@pytest.mark.asyncio
async def test_spoken_language_switch_updates_tts_and_session_state() -> None:
    state = WaypointSessionState()
    tts = RecordingTTS()
    context = FakeRunContext(state, tts)
    assistant = WayPointAssistant()

    hindi_result = await assistant.set_spoken_language(context, "hi")
    english_result = await assistant.set_spoken_language(context, "en")

    assert hindi_result == {
        "active_language": "hi",
        "reply_style": "natural Hinglish with familiar English terms in Latin script",
    }
    assert english_result == {
        "active_language": "en",
        "reply_style": "English",
    }
    assert tts.languages == ["hi", "en"]
    assert state.active_language == "en"


@pytest.mark.asyncio
async def test_spoken_language_switch_fails_without_mutating_state() -> None:
    state = WaypointSessionState()
    context = FakeRunContext(state, object())

    with pytest.raises(ToolError, match="could not be changed"):
        await WayPointAssistant().set_spoken_language(context, "hi")

    assert state.active_language == "en"


def test_prompt_enables_hindi_and_hinglish_without_translating_tool_data() -> None:
    instructions = build_waypoint_instructions()

    assert "Support English and Hindi" in instructions
    assert "natural Hinglish" in instructions
    assert "set_spoken_language with hi" in instructions
    assert "Never produce Hindi or Devanagari text before that tool call" in instructions
    assert "Do not transliterate those English terms into Devanagari" in instructions
    assert "tool arguments" in instructions
