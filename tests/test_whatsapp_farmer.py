import hashlib
import hmac
import json

import pytest
from app.db import Base, build_engine, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-meta-app-secret")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
    from app.core.config import get_settings
    get_settings.cache_clear()
    engine = build_engine(f"sqlite:///{tmp_path / 'whatsapp-test.db'}")
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


def register_and_login(client):
    registered = client.post("/api/v1/auth/register", json={
        "email": "farmer@example.com", "full_name": "Farmer One",
        "password": "secure-pass-123",
    })
    assert registered.status_code == 201, registered.text
    response = client.post("/api/v1/auth/login", json={
        "email": "farmer@example.com", "password": "secure-pass-123",
    })
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_season(client, headers):
    farm = client.post("/api/v1/farm-records/farms", headers=headers, json={
        "farm_name": "Demo Farm", "location": "Lafia, Nasarawa",
        "acreage": 5, "acreage_unit": "hectare", "land_access": "family",
    })
    assert farm.status_code == 201, farm.text
    season = client.post("/api/v1/farm-records/seasons", headers=headers, json={
        "farm_profile_id": farm.json()["id"], "crop_name": "maize",
        "season_name": "2026 rainy season", "planted_area": 3,
        "area_unit": "hectare", "planting_date": "2026-06-01",
    })
    assert season.status_code == 201, season.text


def post_meta_message(client, message):
    payload = {"entry": [{"changes": [{"value": {"messages": [message]}}]}]}
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(
        b"test-meta-app-secret", raw, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/api/v1/whatsapp/webhook", content=raw,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )


def test_whatsapp_number_link_then_confirm_farm_activity(client):
    headers = register_and_login(client)
    create_season(client, headers)
    challenge = client.post(
        "/api/v1/whatsapp/link-challenge", headers=headers,
        json={"phone_e164": "+2348012345678"},
    )
    assert challenge.status_code == 200, challenge.text
    code = challenge.json()["link_code"]

    linked = post_meta_message(client, {
        "id": "wamid.link.1", "from": "2348012345678", "type": "text",
        "text": {"body": f"LINK {code}"},
    })
    assert linked.status_code == 200, linked.text

    recorded = post_meta_message(client, {
        "id": "wamid.activity.1", "from": "2348012345678", "type": "text",
        "text": {"body": "I planted 3 hectares of maize today"},
    })
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["processed_messages"] == 1

    confirmed = post_meta_message(client, {
        "id": "wamid.confirm.1", "from": "2348012345678", "type": "text",
        "text": {"body": "YES"},
    })
    assert confirmed.status_code == 200, confirmed.text
    report = client.get("/api/v1/farm-records/report", headers=headers)
    activities = report.json()["seasons"][0]["activities"]
    assert len(activities) == 1
    assert activities[0]["type"] == "planting"
    assert activities[0]["source_channel"] == "whatsapp"


def test_whatsapp_webhook_rejects_invalid_signature_and_deduplicates(client):
    invalid = client.post(
        "/api/v1/whatsapp/webhook", content=b'{"entry":[]}',
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )
    assert invalid.status_code == 401

    headers = register_and_login(client)
    create_season(client, headers)
    challenge = client.post(
        "/api/v1/whatsapp/link-challenge", headers=headers,
        json={"phone_e164": "+2348012345678"},
    )
    post_meta_message(client, {
        "id": "wamid.link.2", "from": "2348012345678", "type": "text",
        "text": {"body": f"LINK {challenge.json()['link_code']}"},
    })
    message = {
        "id": "wamid.duplicate.1", "from": "2348012345678", "type": "text",
        "text": {"body": "I planted 3 hectares of maize today"},
    }
    first = post_meta_message(client, message)
    second = post_meta_message(client, message)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["processed_messages"] == 0


def test_plant_health_report_returns_cautious_ipm_guidance(client):
    headers = register_and_login(client)
    response = client.post("/api/v1/plant-health/cases", headers=headers, json={
        "crop_name": "tomato", "farm_location": "Warri, Delta",
        "symptoms": "Leaves have yellow spots and some are curling",
        "affected_area_percent": 12, "severity": "moderate",
    })
    assert response.status_code == 201, response.text
    guidance = response.json()["guidance"]
    assert "not a confirmed diagnosis" in guidance["assessment"]
    assert any("Do not spray" in item for item in guidance["pesticide_safety"])
    assert response.json()["status"] == "needs_review"


def test_whatsapp_webhook_verification_challenge(client):
    response = client.get(
        "/api/v1/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "test-verify-token",
                "hub.challenge": "challenge-123"},
    )
    assert response.status_code == 200
    assert response.text == "challenge-123"
