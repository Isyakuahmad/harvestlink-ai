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
    engine = build_engine(f"sqlite:///{tmp_path / 'farm-records.db'}")
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
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def setup_farmer(client, email="farmer@example.com"):
    register(client, email, "Farmer One")
    headers = login(client, email)
    farm = client.post("/api/v1/farm-records/farms", headers=headers, json={
        "farm_name": "Family Farm", "location": "Lafia, Nasarawa",
        "acreage": 4.5, "acreage_unit": "hectare", "land_access": "family",
    })
    assert farm.status_code == 201, farm.text
    season = client.post("/api/v1/farm-records/seasons", headers=headers, json={
        "farm_profile_id": farm.json()["id"], "crop_name": "maize",
        "season_name": "2026 rainy season", "planted_area": 3,
        "area_unit": "hectare", "planting_date": "2026-06-01",
        "expected_harvest_date": "2026-10-15",
    })
    assert season.status_code == 201, season.text
    return headers, season.json()["id"]


def test_farmer_can_create_activity_and_document_supported_evidence(client):
    headers, season_id = setup_farmer(client)
    activity = client.post(
        f"/api/v1/farm-records/seasons/{season_id}/activities",
        headers=headers,
        json={
            "season_id": season_id, "activity_type": "input_purchase",
            "description": "Purchased fertiliser for maize field",
            "activity_date": "2026-06-10", "quantity": 20,
            "quantity_unit": "bags", "amount": 850000, "currency": "NGN",
            "source_channel": "web",
        },
    )
    assert activity.status_code == 201, activity.text
    assert activity.json()["record_confidence"] == "self_reported"
    evidence = client.post(
        f"/api/v1/farm-records/activities/{activity.json()['id']}/evidence",
        headers=headers,
        json={"evidence_type": "receipt", "evidence_uri": "https://files.example/receipt-1",
              "description": "Supplier receipt"},
    )
    assert evidence.status_code == 201
    assert evidence.json()["verification_level"] == "document_supported"
    report = client.get("/api/v1/farm-records/report", headers=headers)
    entry = report.json()["seasons"][0]["activities"][0]
    assert entry["record_confidence"] == "document_supported"
    assert entry["evidence"][0]["verification_level"] == "document_supported"


def test_farmer_records_are_private_and_share_is_scoped_and_revocable(client):
    owner_headers, season_id = setup_farmer(client)
    other_headers, _ = setup_farmer(client, "other@example.com")
    foreign = client.get(
        f"/api/v1/farm-records/seasons/{season_id}/activities",
        headers=other_headers,
    )
    assert foreign.status_code == 404

    share = client.post("/api/v1/farm-records/sharing", headers=owner_headers, json={
        "season_id": season_id, "recipient_name": "Community Microfinance",
        "recipient_type": "microfinance", "purpose": "Seasonal loan application",
        "expires_in_days": 7,
    })
    assert share.status_code == 201, share.text
    token = share.json()["access_token"]
    shared = client.get(f"/api/v1/farm-records/shared/{token}")
    assert shared.status_code == 200
    assert len(shared.json()["report"]["seasons"]) == 1

    grants = client.get("/api/v1/farm-records/sharing", headers=owner_headers)
    grant_id = grants.json()[0]["id"]
    revoked = client.delete(
        f"/api/v1/farm-records/sharing/{grant_id}", headers=owner_headers,
    )
    assert revoked.status_code == 204
    denied = client.get(f"/api/v1/farm-records/shared/{token}")
    assert denied.status_code == 404


def test_only_admin_can_mark_evidence_independently_verified(client):
    farmer_headers, season_id = setup_farmer(client)
    activity = client.post(
        f"/api/v1/farm-records/seasons/{season_id}/activities",
        headers=farmer_headers,
        json={"season_id": season_id, "activity_type": "planting",
              "description": "Planted maize", "activity_date": "2026-06-01"},
    )
    evidence = client.post(
        f"/api/v1/farm-records/activities/{activity.json()['id']}/evidence",
        headers=farmer_headers,
        json={"evidence_type": "photo", "evidence_uri": "https://files.example/field-photo"},
    )
    evidence_id = evidence.json()["id"]
    denied = client.post(
        f"/api/v1/farm-records/admin/evidence/{evidence_id}/verify",
        headers=farmer_headers, params={"reason": "Field evidence inspected"},
    )
    assert denied.status_code == 403

    register(client, "admin@example.com", "Admin User")
    admin_headers = login(client, "admin@example.com")
    verified = client.post(
        f"/api/v1/farm-records/admin/evidence/{evidence_id}/verify",
        headers=admin_headers, params={"reason": "Field evidence inspected in person"},
    )
    assert verified.status_code == 200
    assert verified.json()["verification_level"] == "independently_verified"


def test_invalid_evidence_urls_and_non_farmer_roles_are_rejected(client):
    farmer_headers, season_id = setup_farmer(client)
    activity = client.post(
        f"/api/v1/farm-records/seasons/{season_id}/activities",
        headers=farmer_headers,
        json={"season_id": season_id, "activity_type": "observation",
              "description": "Observed crop growth", "activity_date": date.today().isoformat()},
    )
    invalid = client.post(
        f"/api/v1/farm-records/activities/{activity.json()['id']}/evidence",
        headers=farmer_headers,
        json={"evidence_type": "photo", "evidence_uri": "javascript:alert(1)"},
    )
    assert invalid.status_code == 422

    buyer = client.post("/api/v1/auth/register/buyer", json={
        "email": "buyer@example.com", "full_name": "Buyer One",
        "password": "secure-pass-123", "organization_name": "Buyer Ltd",
        "buyer_type": "processor", "phone": "+2348000000000",
        "location": "Kano, Nigeria",
    })
    assert buyer.status_code == 201
    buyer_headers = login(client, "buyer@example.com")
    denied = client.get("/api/v1/farm-records/farms", headers=buyer_headers)
    assert denied.status_code == 403
