from __future__ import annotations

from app.api.routes.health import health


def test_health() -> None:
    response = health()

    assert response.status == "ok"
    assert response.app_name == "ai-job-AGENT"
