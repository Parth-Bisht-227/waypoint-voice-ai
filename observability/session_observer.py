"""Logging and report persistence for LiveKit agent sessions."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import re
import unicodedata

from livekit.agents import (
    AgentSession,
    ConversationItemAddedEvent,
    JobContext,
    SessionUsageUpdatedEvent,
)
from livekit.agents.llm import ChatMessage


logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
_MAX_ROOM_NAME_LENGTH = 80
_UNSAFE_FILENAME_CHARS = re.compile(r"[^a-z0-9._-]+")


def sanitize_room_name(room_name: str | None) -> str:
    """Return a compact, filesystem-safe room-name component."""

    normalized = unicodedata.normalize("NFKD", room_name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    sanitized = _UNSAFE_FILENAME_CHARS.sub("-", ascii_name).strip("._-")
    sanitized = sanitized[:_MAX_ROOM_NAME_LENGTH].rstrip("._-")
    return sanitized or "unknown-room"


def build_report_filename(
    room_name: str | None,
    *,
    timestamp: datetime | None = None,
) -> str:
    """Build a collision-resistant report filename with a UTC timestamp."""

    timestamp = timestamp or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC)
    utc_component = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    return f"session-{utc_component}-{sanitize_room_name(room_name)}.json"


def attach_session_observers(session: AgentSession) -> None:
    """Attach per-turn latency and cumulative usage logging to a session."""

    def on_conversation_item_added(event: ConversationItemAddedEvent) -> None:
        item = event.item
        if not isinstance(item, ChatMessage):
            return

        if item.role == "user":
            logger.info(
                "user turn metrics transcription_delay=%s end_of_turn_delay=%s",
                item.metrics.get("transcription_delay"),
                item.metrics.get("end_of_turn_delay"),
            )
        elif item.role == "assistant":
            logger.info(
                "assistant turn metrics llm_node_ttft=%s tts_node_ttfb=%s "
                "e2e_latency=%s",
                item.metrics.get("llm_node_ttft"),
                item.metrics.get("tts_node_ttfb"),
                item.metrics.get("e2e_latency"),
            )

    def on_session_usage_updated(event: SessionUsageUpdatedEvent) -> None:
        cumulative_usage = [
            model_usage.model_dump(mode="json", exclude_defaults=True)
            for model_usage in event.usage.model_usage
        ]
        logger.debug("cumulative session usage=%s", cumulative_usage)

    session.on("conversation_item_added", on_conversation_item_added)
    session.on("session_usage_updated", on_session_usage_updated)


async def save_session_report(ctx: JobContext) -> None:
    """Persist a completed report without allowing failures to break shutdown."""

    try:
        report = ctx.make_session_report()
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / build_report_filename(report.room)
        report_json = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        report_path.write_text(f"{report_json}\n", encoding="utf-8")
        logger.info("saved session report to %s", report_path)
    except Exception:
        logger.exception("failed to save session report")
