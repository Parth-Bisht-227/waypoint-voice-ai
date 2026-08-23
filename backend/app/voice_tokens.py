"""Short-lived, room-scoped LiveKit credentials for browser voice sessions."""

from __future__ import annotations

from datetime import timedelta
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from dotenv import dotenv_values
from fastapi import APIRouter, HTTPException, Response, status
from livekit import api

from .schemas import VoiceTokenResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_ENV_PATH = PROJECT_ROOT / "agent" / ".env.local"
TOKEN_TTL = timedelta(minutes=10)
AGENT_NAME = "waypoint-agent"
NO_STORE_HEADERS = {"Cache-Control": "no-store"}
SERVICE_UNAVAILABLE_DETAIL = "Voice sessions are temporarily unavailable."


class VoiceTokenConfigurationError(ValueError):
    """Raised when server-only LiveKit configuration is unavailable or invalid."""


def _configured_value(name: str, local_values: dict[str, str | None]) -> str:
    value = os.getenv(name) or local_values.get(name)
    if not value or not value.strip():
        raise VoiceTokenConfigurationError(f"Missing required setting: {name}")
    return value.strip()


def _validated_server_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"ws", "wss"} or not parsed.netloc:
        raise VoiceTokenConfigurationError("Invalid voice server URL")
    return value


def _load_livekit_configuration() -> tuple[str, str, str]:
    """Load process configuration first, with the ignored local agent env as fallback."""

    local_values = dotenv_values(LOCAL_ENV_PATH)
    server_url = _validated_server_url(
        _configured_value("LIVEKIT_URL", local_values)
    )
    api_key = _configured_value("LIVEKIT_API_KEY", local_values)
    api_secret = _configured_value("LIVEKIT_API_SECRET", local_values)
    return server_url, api_key, api_secret


def _mint_participant_token(
    *,
    api_key: str,
    api_secret: str,
    room_name: str,
    participant_identity: str,
) -> str:
    grants = api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=False,
        can_publish_sources=["microphone"],
    )
    room_config = api.RoomConfiguration(
        agents=[api.RoomAgentDispatch(agent_name=AGENT_NAME)]
    )

    return (
        api.AccessToken(api_key, api_secret)
        .with_identity(participant_identity)
        .with_ttl(TOKEN_TTL)
        .with_grants(grants)
        .with_room_config(room_config)
        .to_jwt()
    )


@router.post("/token", response_model=VoiceTokenResponse)
async def create_voice_token(response: Response) -> VoiceTokenResponse:
    """Issue a unique, short-lived credential for one browser voice room."""

    response.headers.update(NO_STORE_HEADERS)

    try:
        server_url, api_key, api_secret = _load_livekit_configuration()
        room_name = f"waypoint-{uuid4()}"
        participant_identity = f"browser-{uuid4()}"
        participant_token = _mint_participant_token(
            api_key=api_key,
            api_secret=api_secret,
            room_name=room_name,
            participant_identity=participant_identity,
        )
    except Exception:
        logger.warning("Voice token request could not be completed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=SERVICE_UNAVAILABLE_DETAIL,
            headers=NO_STORE_HEADERS,
        ) from None

    return VoiceTokenResponse(
        server_url=server_url,
        participant_token=participant_token,
        room_name=room_name,
        participant_identity=participant_identity,
    )
