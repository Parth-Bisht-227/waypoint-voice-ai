from datetime import UTC, datetime, timedelta, timezone
import json
import logging
from pathlib import Path

import pytest
from livekit.agents import ConversationItemAddedEvent, SessionUsageUpdatedEvent
from livekit.agents.llm import ChatMessage
from livekit.agents.metrics import AgentSessionUsage, LLMModelUsage

from observability import session_observer
from observability.session_observer import (
    attach_session_observers,
    build_report_filename,
    sanitize_room_name,
    save_session_report,
)


@pytest.mark.parametrize(
    ("room_name", "expected"),
    [
        ("Waypoint Support / QA #1", "waypoint-support-qa-1"),
        ("  ../Night\\Shift:?*  ", "night-shift"),
        ("Caf\u00e9 d\u00e9mo", "cafe-demo"),
        ("...", "unknown-room"),
        (None, "unknown-room"),
    ],
)
def test_sanitize_room_name(room_name: str | None, expected: str) -> None:
    assert sanitize_room_name(room_name) == expected


def test_sanitize_room_name_limits_component_length() -> None:
    assert sanitize_room_name("a" * 100) == "a" * 80


def test_build_report_filename_converts_timestamp_to_utc() -> None:
    local_time = datetime(
        2026,
        8,
        23,
        12,
        38,
        9,
        123456,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )

    assert build_report_filename("My / Room", timestamp=local_time) == (
        "session-20260823T070809.123456Z-my-room.json"
    )


class RecordingSession:
    def __init__(self) -> None:
        self.callbacks = {}

    def on(self, event_name, callback):
        self.callbacks[event_name] = callback
        return callback


def test_attach_session_observers_logs_current_livekit_metrics(caplog) -> None:
    session = RecordingSession()
    attach_session_observers(session)

    with caplog.at_level(logging.DEBUG, logger=session_observer.__name__):
        session.callbacks["conversation_item_added"](
            ConversationItemAddedEvent(
                item=ChatMessage(
                    role="user",
                    content=["Hello"],
                    metrics={
                        "transcription_delay": 0.12,
                        "end_of_turn_delay": 0.34,
                    },
                )
            )
        )
        session.callbacks["conversation_item_added"](
            ConversationItemAddedEvent(
                item=ChatMessage(
                    role="assistant",
                    content=["Hi"],
                    metrics={
                        "llm_node_ttft": 0.45,
                        "tts_node_ttfb": 0.56,
                        "e2e_latency": 0.67,
                    },
                )
            )
        )
        session.callbacks["session_usage_updated"](
            SessionUsageUpdatedEvent(
                usage=AgentSessionUsage(
                    model_usage=[
                        LLMModelUsage(
                            provider="gemini",
                            model="gemini-3.5-flash-lite",
                            input_tokens=42,
                        )
                    ]
                )
            )
        )

    assert "transcription_delay=0.12 end_of_turn_delay=0.34" in caplog.text
    assert "llm_node_ttft=0.45 tts_node_ttfb=0.56 e2e_latency=0.67" in caplog.text
    assert "cumulative session usage=" in caplog.text
    assert "input_tokens" in caplog.text


class StubReport:
    room = "Caf\u00e9 / Support"

    def to_dict(self) -> dict:
        return {"room": self.room, "message": "ol\u00e1"}


class StubContext:
    def make_session_report(self) -> StubReport:
        return StubReport()


@pytest.mark.asyncio
async def test_save_session_report_writes_formatted_utf8_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog,
) -> None:
    monkeypatch.setattr(session_observer, "REPORTS_DIR", tmp_path)

    with caplog.at_level(logging.INFO, logger=session_observer.__name__):
        await save_session_report(StubContext())

    report_paths = list(tmp_path.glob("*.json"))
    assert len(report_paths) == 1
    assert report_paths[0].name.endswith("-cafe-support.json")
    report_text = report_paths[0].read_text(encoding="utf-8")
    assert "ol\u00e1" in report_text
    assert '\n  "room":' in report_text
    assert json.loads(report_text) == {"room": "Caf\u00e9 / Support", "message": "ol\u00e1"}
    assert str(report_paths[0]) in caplog.text


class FailingContext:
    def make_session_report(self):
        raise RuntimeError("report unavailable")


@pytest.mark.asyncio
async def test_save_session_report_does_not_break_shutdown(caplog) -> None:
    with caplog.at_level(logging.ERROR, logger=session_observer.__name__):
        await save_session_report(FailingContext())

    assert "failed to save session report" in caplog.text
    assert "report unavailable" in caplog.text
