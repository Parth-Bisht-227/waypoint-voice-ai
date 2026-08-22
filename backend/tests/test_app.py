from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

'''
    TestClient
    → behaves like a fake HTTP client

    client.get(...)
    → sends request directly to FastAPI

    assert
    → checks actual behavior against expected behavior
'''
'''
Whst does assert do exactly?
    assert response.status_code == 200
        means:
    “I expect this condition to be true.”
    If it is true, Python continues.
    If it is false, Python raises an AssertionError, and pytest reports the test as failed.
'''

def test_get_existing_application():
    response = client.get("/applications/APP001")
    assert response.status_code == 200

    data = response.json()

    assert data["application_id"] == "APP001"
    assert data["status"] =="blocked"

def test_get_missing_application():
    response = client.get("/applications/APP999")
    assert response.status_code == 404

def test_get_missing_documents():
    response = client.get("/applications/APP001/missing-documents")

    assert response.status_code == 200
    assert response.json()["missing_documents"] == [
        "bank_statement"
    ]

def test_no_missing_documents():
    response = client.get(
        "/applications/APP002/missing-documents"
    )
    assert response.status_code == 200
    assert response.json()["missing_documents"]==[]

def test_update_travel_date():
    response = client.patch(
        "/applications/APP002/travel-date",
        json = {
            "new_date": "2026-12-01",
            "idempotency_key": "pytest-date-001"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["new_date"] == "2026-12-01"
    assert data["changed"] is True

def test_idempotent_retry_returns_same_result():
    payload = {
        "new_date": "2026-12-05",
        "idempotency_key": "pytest-date-002"
    }

    first = client.patch(
        "/applications/APP003/travel-date",
        json = payload
    )

    second = client.patch(
        "/applications/APP003/travel-date",
        json = payload
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json() == second.json() # we're verifying that the retry
    # receives the original stored result only...

def test_reused_idempotency_key_with_different_request_conflicts():

    first = client.patch(
        "/applications/APP004/travel-date",
        json = {
            "new_date": "2026-12-10",
            "idempotency_key": "pytest-conflict-001"
        }
    )

    second = client.patch(
        "/applications/APP004/travel-date",
        json={
            "new_date": "2026-12-15",
            "idempotency_key": "pytest-conflict-001"
        }
    )
    assert first.status_code == 200
    assert second.status_code == 409


def test_create_handoff():
    response = client.post(
        "/applications/APP001/handoffs",
        json = {
            "reason_code": "user_request"
        }
    )

    assert response.status_code == 201
    data = response.json()

    assert data["application_id"] == "APP001"
    assert data["reason_code"] == "user_request"
    assert data["status"] == "requested"
    assert data["handoff_id"].startswith("HOF-")

def test_handoff_for_missing_application():
    response = client.post(
        "/applications/APP999/handoffs",
        json = {
            "reason_code": "random_reason"
        }
    )
    assert response.status_code == 422


