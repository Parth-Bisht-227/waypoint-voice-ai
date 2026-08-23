"""LiveKit data messages that prompt clients to refresh application state."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import json
import logging
from typing import Literal

from livekit.agents import JobContext


logger = logging.getLogger(__name__)

APPLICATION_SIGNAL_TOPIC = "waypoint.application"
ApplicationSignalType = Literal[
    "application_context",
    "application_updated",
]
ApplicationSignalSender = Callable[[ApplicationSignalType, str], Awaitable[None]]


def encode_application_signal(
    signal_type: ApplicationSignalType,
    application_id: str,
) -> bytes:
    """Encode the intentionally ID-only frontend refresh contract."""

    return json.dumps(
        {
            "type": signal_type,
            "application_id": application_id,
        },
        separators=(",", ":"),
    ).encode("utf-8")


def make_application_signal_sender(ctx: JobContext) -> ApplicationSignalSender:
    """Create a sender backed by the job's public room participant API."""

    async def send(
        signal_type: ApplicationSignalType,
        application_id: str,
    ) -> None:
        await ctx.room.local_participant.publish_data(
            encode_application_signal(signal_type, application_id),
            reliable=True,
            topic=APPLICATION_SIGNAL_TOPIC,
        )

    return send


async def publish_application_signal(
    sender: ApplicationSignalSender | None,
    signal_type: ApplicationSignalType,
    application_id: str,
) -> None:
    """Publish a refresh hint without changing an authoritative tool result."""

    if sender is None:
        return

    try:
        await sender(signal_type, application_id)
    except Exception:
        logger.exception(
            "failed to publish application signal type=%s application_id=%s",
            signal_type,
            application_id,
        )
