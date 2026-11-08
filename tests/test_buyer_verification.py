from datetime import date

import pytest
from app.db import Base, build_engine, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    from app.core.config import get_settings
    get_settings.cache_clear()
    engine = build_engine(f"sqlite:///{tmp_path / 'review.db'}")
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def register(client, email, name):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "full_name": name, "password": "secure-pass-123",
    })
    assert response.status_code == 201, response.text
    return response.json()


def login(client, email):
    response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "secure-pass-123",
    })
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def buyer_register(client, email="buyer@example.com"):
    return client.post("/api/v1/auth/register/buyer", json={
        "email": email, "full_name": "Buyer One", "password": "secure-pass-123",
        "organization_name": "Northern Grain Ltd", "buyer_type": "processor",
        "phone": "+2348000000000", "location": "Kano, Nigeria",
    })


def decide(client, admin_headers, case_id, decision="approve", reason="Documents checked"):
    return client.post(
        f"/api/v1/admin/verification-cases/{case_id}/decision",
        headers=admin_headers,
        json={"decision": decision, "reason": reason},
    )


def test_buyer_onboarding_requires_admin_approval_before_demand(client):
    response = buyer_register(client)
    assert response.status_code == 201, response.text
    register(client, "admin@example.com", "Admin User")
    buyer_headers = login(client, "buyer@example.com")
    requirement = client.post("/api/v1/buyer-requirements", headers=buyer_headers, json={
        "crop_name": "maize", "min_quantity": 5, "unit": "tonne", "location": "Kano",
    })
    assert requirement.status_code == 403

    admin = login(client, "admin@example.com")
    queue = client.get("/api/v1/admin/verification-cases", headers=admin)
    assert queue.status_code == 200
    case = next(item for item in queue.json() if item["subject_type"] == "user")
    assert decide(client, admin, case["id"]).status_code == 200
    requirement = client.post("/api/v1/buyer-requirements", headers=buyer_headers, json={
        "crop_name": "maize", "min_quantity": 5, "unit": "tonne", "location": "Kano",
    })
    assert requirement.status_code == 201


def test_farmer_listing_needs_identity_then_listing_approval(client):
    register(client, "farmer@example.com", "Farmer One")
    farmer_headers = login(client, "farmer@example.com")
    register(client, "admin@example.com", "Admin User")
    admin = login(client, "admin@example.com")
    offer = client.post("/api/v1/workflows/produce-offers", headers=farmer_headers, json={
        "crop_name": "maize", "quantity": 2, "unit": "tonne",
        "quality_description": "Dry maize grain, clean and bagged",
        "location": "Minna, Niger", "available_on": date.today().isoformat(),
    })
    assert offer.status_code == 201, offer.text
    listing_id = offer.json()["listing_id"]
    cases = client.get("/api/v1/admin/verification-cases", headers=admin).json()
    user_case = next(c for c in cases if c["subject_type"] == "user")
    listing_case = next(c for c in cases if c["subject_type"] == "listing")
    blocked = decide(client, admin, listing_case["id"])
    assert blocked.status_code == 409
    assert decide(client, admin, user_case["id"]).status_code == 200
    approved = decide(client, admin, listing_case["id"])
    assert approved.status_code == 200
    history = client.get(
        f"/api/v1/workflows/{offer.json()['workflow_run_id']}", headers=farmer_headers,
    )
    assert history.status_code == 200
    assert history.json()["status"] == "completed"
    assert listing_id == listing_case["subject_id"]


def test_non_admin_cannot_review_and_rejection_is_audited(client):
    register(client, "farmer2@example.com", "Farmer Two")
    farmer_headers = login(client, "farmer2@example.com")
    register(client, "admin@example.com", "Admin User")
    response = client.get("/api/v1/admin/verification-cases", headers=farmer_headers)
    assert response.status_code == 403
    admin = login(client, "admin@example.com")
    case = client.get("/api/v1/admin/verification-cases", headers=admin).json()[0]
    rejected = decide(client, admin, case["id"], "reject", "Identity details did not match")
    assert rejected.status_code == 200
    repeated = decide(client, admin, case["id"])
    assert repeated.status_code == 409


def test_public_registration_cannot_select_admin_or_buyer_role(client):
    response = client.post("/api/v1/auth/register", json={
        "email": "attacker@example.com", "full_name": "Attacker",
        "password": "secure-pass-123", "role": "admin",
    })
    assert response.status_code == 201
    assert response.json()["role"] == "farmer"
