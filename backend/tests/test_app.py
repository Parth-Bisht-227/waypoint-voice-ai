from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import database, main


def future_date(offset_days: int = 0) -> str:
    """Return a stable future ISO date for mutation requests."""
    return (
        date.today() + timedelta(days=365 + offset_days)
    ).isoformat()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Run each test against a freshly seeded temporary SQLite database."""
    test_db_path = tmp_path / "waypoint-test.db"

    async def init_test_db():
        await database.init_db(test_db_path)

    monkeypatch.setattr(main, "DB_PATH", test_db_path)
    monkeypatch.setattr(main, "init_db", init_test_db)

    with TestClient(main.app) as test_client:
        yield test_client


def test_get_existing_application(client: TestClient):
    response = client.get("/applications/APP001")
    assert response.status_code == 200

    data = response.json()

    assert data["application_id"] == "APP001"
    assert data["status"] == "blocked"


def test_get_missing_application(client: TestClient):
    response = client.get("/applications/APP999")
    assert response.status_code == 404


def test_get_missing_documents(client: TestClient):
    response = client.get("/applications/APP001/missing-documents")

    assert response.status_code == 200
    assert response.json()["missing_documents"] == [
        "bank_statement"
    ]


def test_no_missing_documents(client: TestClient):
    response = client.get(
        "/applications/APP002/missing-documents"
    )
    assert response.status_code == 200
    assert response.json()["missing_documents"] == []


def test_update_travel_date(client: TestClient):
    new_date = future_date()

    response = client.patch(
        "/applications/APP002/travel-date",
        json={
            "new_date": new_date,
            "idempotency_key": "pytest-date-001",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["new_date"] == new_date
    assert data["changed"] is True


def test_idempotent_retry_returns_same_result(client: TestClient):
    payload = {
        "new_date": future_date(1),
        "idempotency_key": "pytest-date-002",
    }

    first = client.patch(
        "/applications/APP003/travel-date",
        json=payload,
    )

    second = client.patch(
        "/applications/APP003/travel-date",
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json() == second.json()


def test_reused_idempotency_key_with_different_request_conflicts(
    client: TestClient,
):
    first = client.patch(
        "/applications/APP004/travel-date",
        json={
            "new_date": future_date(2),
            "idempotency_key": "pytest-conflict-001",
        },
    )

    second = client.patch(
        "/applications/APP004/travel-date",
        json={
            "new_date": future_date(3),
            "idempotency_key": "pytest-conflict-001",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 409


def test_create_handoff(client: TestClient):
    response = client.post(
        "/applications/APP001/handoffs",
        json={
            "reason_code": "user_request",
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["application_id"] == "APP001"
    assert data["reason_code"] == "user_request"
    assert data["status"] == "requested"
    assert data["handoff_id"].startswith("HOF-")


def test_handoff_for_missing_application(client: TestClient):
    response = client.post(
        "/applications/APP999/handoffs",
        json={
            "reason_code": "random_reason",
        },
    )
    assert response.status_code == 422
