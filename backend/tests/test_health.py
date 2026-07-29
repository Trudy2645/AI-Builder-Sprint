from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.health import check_database_connection
from app.core.config import Settings, get_settings


def test_liveness_returns_success_envelope(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}
    assert response.json()["meta"]["request_id"] == response.headers["X-Request-Id"]


def test_liveness_preserves_caller_request_id(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-Id": "test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "test-request"


def test_readiness_succeeds_when_database_is_available(app: FastAPI, client: TestClient) -> None:
    async def database_is_available() -> None:
        return None

    app.dependency_overrides[check_database_connection] = database_is_available

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ready", "database": "connected"}


def test_readiness_fails_when_database_is_not_configured(app: FastAPI, client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(database_url=None)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_NOT_CONFIGURED"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-Id"]
