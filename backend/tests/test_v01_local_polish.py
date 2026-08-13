from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_v01_account_config_resume import _register_and_login
from tests.test_v01_account_config_resume import client as client


def test_error_response_contains_request_id_and_stable_shape(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"X-Request-ID": "req-test-001"},
    )

    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == "req-test-001"
    assert response.json() == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Not authenticated",
            "request_id": "req-test-001",
        }
    }


def test_validation_error_uses_unified_error_shape(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers={"X-Request-ID": "req-validation-001"},
        json={"email": "bad-email"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "请求参数不符合要求。"
    assert body["error"]["request_id"] == "req-validation-001"
    assert body["error"]["details"]


def test_task_status_exposes_local_runner_and_celery_state(client: TestClient) -> None:
    token = _register_and_login(client, "task-status@example.com")
    response = client.get(
        "/api/v1/tasks/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    statuses = {item["backend"]: item for item in response.json()}
    assert statuses["in-process"]["status"] == "running"
    assert statuses["celery"]["status"] == "not_enabled"
