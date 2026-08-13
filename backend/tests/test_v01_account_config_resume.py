from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with tempfile.TemporaryDirectory() as tmp_dir:
        old_resume_dir = settings.resume_storage_dir
        settings.resume_storage_dir = tmp_dir

        def override_get_db() -> Generator[Session, None, None]:
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        settings.resume_storage_dir = old_resume_dir


def _register_and_login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_auth_profile_model_provider_and_resume_upload(client: TestClient) -> None:
    token = _register_and_login(client, "student@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "student@example.com"

    profile = client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "target_role": "Agent 开发实习生",
            "salary_min": 150,
            "salary_max": 300,
            "cities": "杭州,上海",
            "work_type": "internship",
            "deal_breakers": "不接受长期无薪实习",
        },
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["target_role"] == "Agent 开发实习生"

    provider = client.post(
        "/api/v1/model-providers",
        headers=headers,
        json={
            "provider": "openai",
            "api_key": "sk-local-test-demo",
            "model_name": "gpt-4.1-mini",
            "base_url": "https://api.openai.com/v1",
            "timeout_seconds": 10,
            "network_mode": "auto",
        },
    )
    assert provider.status_code == 200, provider.text
    assert provider.json()["masked_api_key"] == "sk-l...demo"
    assert provider.json()["network_mode"] == "auto"

    test_response = client.post(
        f"/api/v1/model-providers/{provider.json()['id']}/test",
        headers=headers,
    )
    assert test_response.status_code == 200
    assert test_response.json()["ok"] is True

    resume = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("resume.md", b"# Resume\nPython FastAPI Agent project", "text/markdown")},
    )
    assert resume.status_code == 201, resume.text
    body = resume.json()
    assert body["is_default"] is True
    assert "FastAPI Agent" in body["versions"][0]["extracted_text"]
    assert Path(settings.resume_storage_dir).exists()


def test_user_isolation_for_resumes(client: TestClient) -> None:
    token_a = _register_and_login(client, "a@example.com")
    token_b = _register_and_login(client, "b@example.com")

    resume = client.post(
        "/api/v1/resumes/upload",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("resume.md", b"A private resume", "text/markdown")},
    )
    assert resume.status_code == 201

    forbidden = client.get(
        f"/api/v1/resumes/{resume.json()['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden.status_code == 404


def test_model_provider_can_be_deleted(client: TestClient) -> None:
    token = _register_and_login(client, "delete-provider@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    provider = client.post(
        "/api/v1/model-providers",
        headers=headers,
        json={
            "provider": "deepseek",
            "api_key": "sk-local-test-delete-provider",
            "model_name": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "timeout_seconds": 30,
            "network_mode": "auto",
        },
    )
    assert provider.status_code == 200, provider.text

    delete_response = client.delete(
        f"/api/v1/model-providers/{provider.json()['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    providers = client.get("/api/v1/model-providers", headers=headers)
    assert providers.status_code == 200
    assert providers.json() == []


def test_resume_can_be_deleted_and_default_moves_to_remaining_resume(
    client: TestClient,
) -> None:
    token = _register_and_login(client, "delete-resume@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first_resume = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("first.md", b"First resume Python Agent", "text/markdown")},
    )
    assert first_resume.status_code == 201, first_resume.text
    second_resume = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={"file": ("second.md", b"Second resume Java Spring", "text/markdown")},
    )
    assert second_resume.status_code == 201, second_resume.text

    uploaded_resumes = client.get("/api/v1/resumes", headers=headers)
    assert uploaded_resumes.status_code == 200
    assert len(uploaded_resumes.json()) == 2
    uploaded_files = [
        path for path in Path(settings.resume_storage_dir).rglob("*") if path.is_file()
    ]
    assert len(uploaded_files) == 2
    default_resume = next(item for item in uploaded_resumes.json() if item["is_default"])
    assert default_resume["id"] == first_resume.json()["id"]

    delete_response = client.delete(
        f"/api/v1/resumes/{first_resume.json()['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    remaining = client.get("/api/v1/resumes", headers=headers)
    assert remaining.status_code == 200
    body = remaining.json()
    assert len(body) == 1
    assert body[0]["id"] == second_resume.json()["id"]
    assert body[0]["is_default"] is True
    assert Path(settings.resume_storage_dir).exists()
    remaining_files = [
        path for path in Path(settings.resume_storage_dir).rglob("*") if path.is_file()
    ]
    assert len(remaining_files) == 1
    assert remaining_files[0].name.startswith("second_")
