from app.main import app
from fastapi.testclient import TestClient


def test_dashboard_is_served():
    response = TestClient(app).get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "HarvestLink AI" in response.text
    assert 'id="login"' in response.text
