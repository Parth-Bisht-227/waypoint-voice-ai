from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.app import database, main, voice_tokens


API_KEY = "test-livekit-key"
API_SECRET = "test-livekit-secret-with-at-least-32-bytes"
SERVER_URL = "wss://voice.example.test"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Start FastAPI with isolated storage and deterministic dummy credentials."""

    test_db_path = tmp_path / "waypoint-token-test.db"
    missing_env_path = tmp_path / "missing.env"

    async def init_test_db():
        await database.init_db(test_db_path)

    monkeypatch.setattr(main, "DB_PATH", test_db_path)
    monkeypatch.setattr(main, "init_db", init_test_db)
    monkeypatch.setattr(voice_tokens, "LOCAL_ENV_PATH", missing_env_path)
    monkeypatch.setenv("LIVEKIT_URL", SERVER_URL)
    monkeypatch.setenv("LIVEKIT_API_KEY", API_KEY)
    monkeypatch.setenv("LIVEKIT_API_SECRET", API_SECRET)

    with TestClient(main.app) as test_client:
        yield test_client


def decode_token(
    participant_token: str,
    *,
    api_key: str = API_KEY,
    api_secret: str = API_SECRET,
) -> dict:
    return jwt.decode(
        participant_token,
        api_secret,
        algorithms=["HS256"],
        issuer=api_key,
    )


def test_voice_token_contains_short_lived_room_scoped_claims(client: TestClient):
    response = client.post("/voice/token")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"

    body = response.json()
    assert body["server_url"] == SERVER_URL
    assert body["room_name"].startswith("waypoint-")
    assert body["participant_identity"].startswith("browser-")

    claims = decode_token(body["participant_token"])
    assert claims["iss"] == API_KEY
    assert claims["sub"] == body["participant_identity"]
    assert 599 <= claims["exp"] - claims["nbf"] <= 601
    assert claims["video"] == {
        "roomJoin": True,
        "room": body["room_name"],
        "canPublish": True,
        "canSubscribe": True,
        "canPublishData": False,
        "canPublishSources": ["microphone"],
    }
    assert claims["roomConfig"] == {
        "agents": [{"agentName": "waypoint-agent"}]
    }


def test_voice_token_requests_are_unique(client: TestClient):
    first = client.post("/voice/token")
    second = client.post("/voice/token")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["room_name"] != second.json()["room_name"]
    assert (
        first.json()["participant_identity"]
        != second.json()["participant_identity"]
    )
    assert first.json()["participant_token"] != second.json()["participant_token"]


@pytest.mark.parametrize(
    ("missing_name", "invalid_url"),
    [
        ("LIVEKIT_API_KEY", False),
        ("LIVEKIT_API_SECRET", False),
        ("LIVEKIT_URL", False),
        (None, True),
    ],
)
def test_voice_token_configuration_failures_do_not_disclose_details(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str | None,
    invalid_url: bool,
):
    if missing_name:
        monkeypatch.delenv(missing_name)
    if invalid_url:
        monkeypatch.setenv("LIVEKIT_URL", "https://not-a-websocket.example.test")

    response = client.post("/voice/token")

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    response_text = response.text.lower()
    assert response.json() == {
        "detail": "Voice sessions are temporarily unavailable."
    }
    assert API_KEY.lower() not in response_text
    assert API_SECRET.lower() not in response_text
    assert SERVER_URL.lower() not in response_text
    assert "livekit" not in response_text
    assert "api_key" not in response_text
    assert "api_secret" not in response_text


def test_process_environment_takes_precedence_over_local_fallback(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fallback_path = tmp_path / "agent.env"
    fallback_path.write_text(
        "LIVEKIT_URL=wss://fallback.example.test\n"
        "LIVEKIT_API_KEY=fallback-key\n"
        "LIVEKIT_API_SECRET=fallback-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(voice_tokens, "LOCAL_ENV_PATH", fallback_path)

    response = client.post("/voice/token")

    assert response.status_code == 200
    assert response.json()["server_url"] == SERVER_URL
    assert decode_token(response.json()["participant_token"])["iss"] == API_KEY


def test_local_agent_environment_is_used_as_a_development_fallback(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fallback_url = "ws://127.0.0.1:7880"
    fallback_key = "fallback-key"
    fallback_secret = "fallback-secret-with-at-least-32-bytes"
    fallback_path = tmp_path / "agent.env"
    fallback_path.write_text(
        f"LIVEKIT_URL={fallback_url}\n"
        f"LIVEKIT_API_KEY={fallback_key}\n"
        f"LIVEKIT_API_SECRET={fallback_secret}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(voice_tokens, "LOCAL_ENV_PATH", fallback_path)
    monkeypatch.delenv("LIVEKIT_URL")
    monkeypatch.delenv("LIVEKIT_API_KEY")
    monkeypatch.delenv("LIVEKIT_API_SECRET")

    response = client.post("/voice/token")

    assert response.status_code == 200
    assert response.json()["server_url"] == fallback_url
    claims = decode_token(
        response.json()["participant_token"],
        api_key=fallback_key,
        api_secret=fallback_secret,
    )
    assert claims["iss"] == fallback_key
