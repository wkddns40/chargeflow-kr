from fastapi.testclient import TestClient

from app.main import create_app


def test_root_status() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "chargeflow-kr-api"}


def test_healthz() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
