from datetime import date, timedelta

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
    engine = build_engine(f"sqlite:///{tmp_path / 'procurement.db'}")
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


def account(client, email, name, buyer=False):
    password = "secure-pass-123"
    if buyer:
        response = client.post("/api/v1/auth/register/buyer", json={
            "email": email, "full_name": name, "password": password,
            "organization_name": "Buyer Organisation", "buyer_type": "exporter",
            "phone": "+2348000000000", "location": "Lafia, Nasarawa",
        })
    else:
        response = client.post("/api/v1/auth/register", json={
            "email": email, "full_name": name, "password": password,
        })
    assert response.status_code == 201, response.text
    admin_response = client.post("/api/v1/auth/register", json={
        "email": "admin@example.com", "full_name": "Admin User", "password": password,
    })
    assert admin_response.status_code in {201, 409}
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com", "password": password,
    })
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    queue = client.get("/api/v1/admin/verification-cases", headers=admin_headers).json()
    case = next(x for x in queue if x["subject_type"] == "user" and x["subject"]["email"] == email)
    approved = client.post(
        f"/api/v1/admin/verification-cases/{case['id']}/decision",
        headers=admin_headers, json={"decision": "approve", "reason": "Identity checked for test"},
    )
    assert approved.status_code == 200, approved.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def approve_listing(client, admin_headers, listing_id):
    queue = client.get("/api/v1/admin/verification-cases", headers=admin_headers).json()
    case = next(x for x in queue if x["subject_type"] == "listing" and x["subject_id"] == listing_id)
    response = client.post(
        f"/api/v1/admin/verification-cases/{case['id']}/decision",
        headers=admin_headers, json={"decision": "approve", "reason": "Listing details reviewed"},
    )
    assert response.status_code == 200, response.text


def test_buyer_interest_farmer_response_and_confirmed_transaction(client):
    farmer = account(client, "farmer@demo.test", "Farmer Demo")
    buyer = account(client, "buyer@demo.test", "Buyer Demo", buyer=True)
    password = "secure-pass-123"
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com", "password": password,
    })
    admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    req = client.post("/api/v1/buyer-requirements", headers=buyer, json={
        "crop_name": "sesame", "min_quantity": 1, "max_quantity": 5,
        "unit": "tonne", "location": "Nasarawa",
    })
    assert req.status_code == 201, req.text
    offer = client.post("/api/v1/workflows/produce-offers", headers=farmer, json={
        "crop_name": "sesame", "quantity": 3000, "unit": "kg",
        "quality_description": "Clean dry sesame", "location": "Lafia, Nasarawa",
        "available_on": (date.today() + timedelta(days=10)).isoformat(),
    })
    assert offer.status_code == 201, offer.text
    approve_listing(client, admin, offer.json()["listing_id"])

    matches = client.get("/api/v1/marketplace/matches", headers=buyer)
    assert matches.status_code == 200, matches.text
    assert len(matches.json()) == 1
    match_id = matches.json()[0]["match_id"]
    interest = client.post(
        f"/api/v1/marketplace/matches/{match_id}/interest", headers=buyer,
        json={"message": "We are interested in this sesame lot"},
    )
    assert interest.status_code == 201, interest.text
    interest_id = interest.json()["id"]

    farmer_interests = client.get("/api/v1/interests", headers=farmer)
    assert farmer_interests.status_code == 200
    assert farmer_interests.json()[0]["id"] == interest_id
    response = client.post(f"/api/v1/interests/{interest_id}/response", headers=farmer, json={
        "decision": "accept", "message": "The lot is available for discussion",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

    terms = client.post(f"/api/v1/interests/{interest_id}/terms", headers=buyer, json={
        "quantity": 2, "unit": "tonne", "price_per_unit": 1500000,
        "currency": "NGN", "delivery_location": "Lafia warehouse",
        "delivery_date": (date.today() + timedelta(days=20)).isoformat(),
    })
    assert terms.status_code == 201, terms.text
    tx_id = terms.json()["id"]
    assert terms.json()["status"] == "terms_proposed"

    confirmed = client.post(f"/api/v1/transactions/{tx_id}/confirm", headers=farmer)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["terms"]["price_per_unit"] == 1500000

    hidden = client.get(f"/api/v1/transactions/{tx_id}", headers=account(
        client, "intruder@demo.test", "Intruder"
    ))
    assert hidden.status_code == 404

    delivered = client.post(
        f"/api/v1/transactions/{tx_id}/delivery", headers=buyer,
        json={"message": "Buyer confirmed delivery at the agreed location"},
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == "delivered"
