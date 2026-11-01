import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from app.db import Base, build_engine, get_db
from app.main import app

@pytest.fixture
def client(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    def override_db():
        db = factory()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear(); Base.metadata.drop_all(bind=engine); engine.dispose()

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200 and response.json()["status"] == "ok"

def test_register_duplicate_login_me(client):
    data = {"email":"farmer@example.com", "full_name":"Amina Farmer", "password":"secure-pass-123"}
    assert client.post("/api/v1/auth/register", json=data).status_code == 201
    assert client.post("/api/v1/auth/register", json=data).status_code == 409
    login = client.post("/api/v1/auth/login", json={"email":"FARMER@example.com", "password":data["password"]})
    assert login.status_code == 200
    token = login.json()["access_token"]
    profile = client.get("/api/v1/auth/me", headers={"Authorization":f"Bearer {token}"})
    assert profile.status_code == 200 and profile.json()["role"] == "farmer"

def test_wrong_password(client):
    client.post("/api/v1/auth/register", json={"email":"buyer@example.com", "full_name":"Buyer Person", "password":"secure-pass-123"})
    response = client.post("/api/v1/auth/login", json={"email":"buyer@example.com", "password":"wrong-password"})
    assert response.status_code == 401
