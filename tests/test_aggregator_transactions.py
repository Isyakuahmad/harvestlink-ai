from app.db import Base, build_engine, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker


def test_aggregator_offer_accept_reserves_and_prevents_oversell(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    from app.core.config import get_settings
    get_settings.cache_clear()
    engine = build_engine(f"sqlite:///{tmp_path / 'aggregator-deals.db'}")
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        password = "secure-pass-123"
        admin_register = client.post("/api/v1/auth/register", json={
            "email": "admin@example.com", "full_name": "Admin", "password": password,
        })
        assert admin_register.status_code in {201, 409}
        admin_login = client.post("/api/v1/auth/login", json={
            "email": "admin@example.com", "password": password,
        })
        admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        def verified_buyer(email, name, buyer_type):
            registered = client.post("/api/v1/auth/register/buyer", json={
                "email": email, "full_name": name, "password": password,
                "organization_name": name + " Ltd", "buyer_type": buyer_type,
                "phone": "+2348000000000", "location": "Lafia, Nigeria",
            })
            assert registered.status_code == 201, registered.text
            cases = client.get("/api/v1/admin/verification-cases", headers=admin).json()
            case = next(item for item in cases if item["subject_type"] == "user"
                        and item["subject"]["email"] == email)
            approved = client.post(
                f"/api/v1/admin/verification-cases/{case['id']}/decision",
                headers=admin, json={"decision": "approve", "reason": "Test account reviewed"},
            )
            assert approved.status_code == 200, approved.text
            login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
            return {"Authorization": f"Bearer {login.json()['access_token']}"}

        aggregator = verified_buyer("aggregator@example.com", "Aggregator", "aggregator")
        buyer_a = verified_buyer("buyer-a@example.com", "Buyer A", "exporter")
        buyer_b = verified_buyer("buyer-b@example.com", "Buyer B", "processor")
        stock = client.post("/api/v1/aggregator/stock", headers=aggregator, json={
            "crop_name": "sesame", "quantity": 10, "unit": "tonne",
            "quality_description": "Clean dry sesame", "location": "Lafia, Nigeria",
            "ownership_reference": "STORE-LOT-001",
        })
        assert stock.status_code == 201, stock.text
        lot_id = stock.json()["id"]

        offers = []
        for buyer, email in ((buyer_a, "buyer-a"), (buyer_b, "buyer-b")):
            response = client.post(f"/api/v1/aggregator/stock/{lot_id}/offers",
                headers=buyer, json={"quantity": 7, "unit": "tonne",
                    "price_per_unit": 1400000, "currency": "ngn", "message": email})
            assert response.status_code == 201, response.text
            offers.append(response.json()["id"])

        accepted = client.post(f"/api/v1/aggregator/stock/offers/{offers[0]}/decision",
            headers=aggregator, json={"decision": "accept", "message": "Terms accepted"})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "reserved"
        assert accepted.json()["total_value"] == 9800000

        oversell = client.post(f"/api/v1/aggregator/stock/offers/{offers[1]}/decision",
            headers=aggregator, json={"decision": "accept"})
        assert oversell.status_code == 409, oversell.text

        cancelled = client.post(f"/api/v1/aggregator/stock/deals/{accepted.json()['deal_id']}/cancel",
            headers=buyer_a)
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["released_quantity"] == 7

        retry = client.post(f"/api/v1/aggregator/stock/offers/{offers[1]}/decision",
            headers=aggregator, json={"decision": "accept"})
        assert retry.status_code == 200, retry.text

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()
