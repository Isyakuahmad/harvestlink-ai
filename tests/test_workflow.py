from datetime import date, timedelta

import pytest
from app.db import Base, build_engine, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path):
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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def register_and_login(client, email, full_name):
    payload = {"email": email, "full_name": full_name, "password": "secure-pass-123"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": payload["password"]},
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
        headers=farmer_headers,
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
    assert offer.status_code == 201, offer.text
    result = offer.json()
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
        headers=farmer_headers,
        json={
            "crop_name": "sesame",
            "quantity": 2,
            "unit": "tonne",
            "quality_description": "Cleaned sesame seeds",
            "location": "Lafia, Nasarawa",
            "available_on": date.today().isoformat(),
        },
    )
    assert response.status_code == 201
    assert response.json()["matches"][0]["eligible"] is False


def test_workflow_history_is_private_to_the_farmer(client):
    farmer_headers = register_and_login(client, "owner@example.com", "Owner Farmer")
    other_headers = register_and_login(client, "other@example.com", "Other Farmer")
    response = client.post(
        "/api/v1/workflows/produce-offers",
        headers=farmer_headers,
        json={
            "crop_name": "maize",
            "quantity": 2,
            "unit": "tonne",
            "quality_description": "Dry maize grain",
            "location": "Minna, Niger",
            "available_on": date.today().isoformat(),
        },
    )
    run_id = response.json()["workflow_run_id"]
    hidden = client.get(f"/api/v1/workflows/{run_id}", headers=other_headers)
    assert hidden.status_code == 404


def test_offer_requires_authentication(client):
    response = client.post("/api/v1/workflows/produce-offers", json={})
    assert response.status_code == 401
