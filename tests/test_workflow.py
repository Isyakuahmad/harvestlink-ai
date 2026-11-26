from datetime import UTC, date, datetime, timedelta

import pytest
from app.db import Base, build_engine, get_db
from app.main import app
from app.models import User, WorkflowRun
from app.workflow_execution import run_pending_once
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    from app.core.config import get_settings
    get_settings.cache_clear()
    engine = build_engine(f"sqlite:///{tmp_path / 'workflow.db'}")
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.state.workflow_session_factory = factory
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def register_and_login(client, email, full_name):
    password = "secure-pass-123"
    if full_name.startswith("Buyer"):
        response = client.post("/api/v1/auth/register/buyer", json={
            "email": email, "full_name": full_name, "password": password,
            "organization_name": "Test Buyer Ltd", "buyer_type": "processor",
            "phone": "+2348000000000", "location": "Nasarawa",
        })
        assert response.status_code == 201, response.text
        admin_registration = client.post("/api/v1/auth/register", json={
            "email": "admin@example.com", "full_name": "Test Admin", "password": password,
        })
        assert admin_registration.status_code in {201, 409}
        admin_login = client.post("/api/v1/auth/login", json={
            "email": "admin@example.com", "password": password,
        })
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
        queue = client.get("/api/v1/admin/verification-cases", headers=admin_headers)
        buyer_case = next(
            item for item in queue.json()
            if item["subject_type"] == "user" and item["subject"]["email"] == email
        )
        approved = client.post(
            f"/api/v1/admin/verification-cases/{buyer_case['id']}/decision",
            headers=admin_headers,
            json={"decision": "approve", "reason": "Test buyer verified"},
        )
        assert approved.status_code == 200, approved.text
    else:
        payload = {"email": email, "full_name": full_name, "password": password}
        assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_farmer_trust_matching_orchestrator_flow(client):
    farmer_headers = register_and_login(client, "farmer@example.com", "Farmer One")
    buyer_headers = register_and_login(client, "buyer@example.com", "Buyer One")

    requirement = client.post(
        "/api/v1/buyer-requirements",
        headers=buyer_headers,
        json={
            "crop_name": "white sesame",
            "min_quantity": 10,
            "max_quantity": 30,
            "unit": "tonne",
            "quality_requirements": "machine cleaned",
            "location": "Nasarawa",
            "max_price": 1800000,
            "currency": "NGN",
        },
    )
    assert requirement.status_code == 201

    offer = client.post(
        "/api/v1/workflows/produce-offers",
        headers={**farmer_headers, "Idempotency-Key": "workflow-test-1-key"},
        json={
            "crop_name": "White Sesame",
            "quantity": 20000,
            "unit": "kg",
            "quality_description": "Machine cleaned white sesame, moisture below 8 percent",
            "location": "Lafia, Nasarawa",
            "available_on": (date.today() + timedelta(days=15)).isoformat(),
            "asking_price": 1500000,
            "currency": "NGN",
        },
    )
    assert offer.status_code == 202, offer.text
    queued = offer.json()
    assert queued["status"] == "queued"
    run_pending_once(client.app.state.workflow_session_factory)
    history_response = client.get(
        f"/api/v1/workflows/{queued['workflow_run_id']}", headers=farmer_headers
    )
    result = history_response.json()["result"]
    assert result["workflow_status"] == "completed"
    assert result["listing_status"] == "pending_review"
    assert result["trust"]["identity_status"] == "unverified"
    assert result["trust"]["can_publish"] is False
    assert result["trust"]["can_contact_buyer"] is False
    assert len(result["matches"]) == 1
    assert result["matches"][0]["eligible"] is True
    assert result["matches"][0]["score"] == 100.0

    history = client.get(
        f"/api/v1/workflows/{result['workflow_run_id']}",
        headers=farmer_headers,
    )
    assert history.status_code == 200
    assert history.json()["status"] == "completed"
    assert [task["agent_name"] for task in history.json()["agent_tasks"]] == [
        "farmer",
        "trust",
        "buyer_matching",
        "orchestrator",
    ]


def test_incompatible_crop_is_not_matched(client):
    farmer_headers = register_and_login(client, "farmer2@example.com", "Farmer Two")
    buyer_headers = register_and_login(client, "buyer2@example.com", "Buyer Two")
    client.post(
        "/api/v1/buyer-requirements",
        headers=buyer_headers,
        json={
            "crop_name": "rice",
            "min_quantity": 1,
            "unit": "tonne",
            "location": "Nasarawa",
        },
    )
    response = client.post(
        "/api/v1/workflows/produce-offers",
        headers={**farmer_headers, "Idempotency-Key": "workflow-test-2-key"},
        json={
            "crop_name": "sesame",
            "quantity": 2,
            "unit": "tonne",
            "quality_description": "Cleaned sesame seeds",
            "location": "Lafia, Nasarawa",
            "available_on": date.today().isoformat(),
        },
    )
    assert response.status_code == 202
    run_pending_once(client.app.state.workflow_session_factory)
    completed = client.get(
        f"/api/v1/workflows/{response.json()['workflow_run_id']}", headers=farmer_headers
    ).json()["result"]
    assert completed["matches"][0]["eligible"] is False


def test_workflow_history_is_private_to_the_farmer(client):
    farmer_headers = register_and_login(client, "owner@example.com", "Owner Farmer")
    other_headers = register_and_login(client, "other@example.com", "Other Farmer")
    response = client.post(
        "/api/v1/workflows/produce-offers",
        headers={**farmer_headers, "Idempotency-Key": "workflow-test-3-key"},
        json={
            "crop_name": "maize",
            "quantity": 2,
            "unit": "tonne",
            "quality_description": "Dry maize grain",
            "location": "Minna, Niger",
            "available_on": date.today().isoformat(),
        },
    )
    assert response.status_code == 202
    run_id = response.json()["workflow_run_id"]
    run_pending_once(client.app.state.workflow_session_factory)
    hidden = client.get(f"/api/v1/workflows/{run_id}", headers=other_headers)
    assert hidden.status_code == 404




def test_offer_submission_is_idempotent_and_rejects_key_reuse(client):
    headers = register_and_login(client, "idempotent@example.com", "Idempotent Farmer")
    headers = {**headers, "Idempotency-Key": "same-request-key-123"}
    payload = {
        "crop_name": "maize",
        "quantity": 5,
        "unit": "tonne",
        "quality_description": "Clean dry maize grain",
        "location": "Warri, Delta",
        "available_on": date.today().isoformat(),
    }
    first = client.post(
        "/api/v1/workflows/produce-offers", headers=headers, json=payload
    )
    second = client.post(
        "/api/v1/workflows/produce-offers", headers=headers, json=payload
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["workflow_run_id"] == second.json()["workflow_run_id"]
    assert second.json()["duplicate_request"] is True

    changed = {**payload, "quantity": 6}
    conflict = client.post(
        "/api/v1/workflows/produce-offers", headers=headers, json=changed
    )
    assert conflict.status_code == 409


def test_workflow_retries_and_exposes_manual_retry_after_exhaustion(client):
    headers = register_and_login(client, "retry@example.com", "Retry Farmer")
    factory = client.app.state.workflow_session_factory
    db = factory()
    try:
        farmer = db.query(User).filter(User.email == "retry@example.com").one()
        run = WorkflowRun(
            farmer_user_id=farmer.id,
            idempotency_key="retry-test-key-123",
            request_hash="bad-request-hash",
            status="queued",
            result_json={"request": {"invalid": "payload"}},
            attempt_count=0,
            max_attempts=2,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    finally:
        db.close()

    run_pending_once(factory)
    db = factory()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).one()
        assert run.status == "retrying"
        assert run.attempt_count == 1
        run.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    run_pending_once(factory)
    db = factory()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).one()
        assert run.status == "failed"
        assert run.attempt_count == 2
    finally:
        db.close()

    retry = client.post(f"/api/v1/workflows/{run_id}/retry", headers=headers)
    assert retry.status_code == 202
    assert retry.json()["status"] == "queued"


def test_offer_requires_authentication(client):
    response = client.post("/api/v1/workflows/produce-offers", headers={"Idempotency-Key": "no-auth-key-123"}, json={})
    assert response.status_code == 401
