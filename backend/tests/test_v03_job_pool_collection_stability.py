from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.test_v01_account_config_resume import _register_and_login
from tests.test_v01_account_config_resume import client as client
from tests.test_v01_job_evaluation import _create_job_for_user, _setup_profile_and_resume


def test_job_pool_metadata_filters_and_interview_status_flow(client: TestClient) -> None:
    token = _register_and_login(client, "v03-pool-meta@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(
        client,
        token,
        title="AI Agent 开发工程师",
        company="稳定性测试公司",
        location="杭州",
        description="负责 AI Agent、RAG、Python 和 FastAPI 后端开发。",
    )
    add_to_pool = client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers)
    assert add_to_pool.status_code == 200, add_to_pool.text
    assert add_to_pool.json()["application_status"] == "CONFIRMED"

    resume_version = client.get("/api/v1/resumes", headers=headers).json()[0]["versions"][0]
    update = client.patch(
        f"/api/v1/jobs/{job_id}/pool",
        headers=headers,
        json={
            "application_status": "APPLIED",
            "applied_at": "2026-08-14T09:30:00+08:00",
            "application_resume_version_id": resume_version["id"],
            "contact_name": "Linda HR",
            "notes": "已通过官网投递，等待一面。",
        },
    )
    assert update.status_code == 200, update.text
    body = update.json()
    assert body["application_status"] == "APPLIED"
    assert body["application_resume_version_id"] == resume_version["id"]
    assert body["application_resume_title"] == resume_version["title"]
    assert body["contact_name"] == "Linda HR"
    assert body["notes"] == "已通过官网投递，等待一面。"
    assert body["status_changed_at"] is not None

    assert _pool_ids(client, headers, "status=APPLIED") == [job_id]
    assert _pool_ids(client, headers, "company=稳定性") == [job_id]
    assert _pool_ids(client, headers, "city=杭州") == [job_id]
    assert _pool_ids(client, headers, "keyword=FastAPI") == [job_id]

    start = client.post(
        "/api/v1/interviews",
        headers=headers,
        json={"job_id": job_id, "max_questions": 1},
    )
    assert start.status_code == 200, start.text
    pool_after_start = client.get("/api/v1/jobs/pool", headers=headers).json()
    assert pool_after_start[0]["application_status"] == "INTERVIEWING"

    finish = client.post(f"/api/v1/interviews/{start.json()['id']}/finish", headers=headers)
    assert finish.status_code == 200, finish.text
    pool_after_finish = client.get("/api/v1/jobs/pool", headers=headers).json()
    assert pool_after_finish[0]["application_status"] == "REVIEWED"


def _pool_ids(client: TestClient, headers: dict[str, str], query: str) -> list[str]:
    response = client.get(f"/api/v1/jobs/pool?{query}", headers=headers)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def test_collection_idempotency_source_id_dedup_and_failure_no_write(
    client: TestClient,
) -> None:
    token = _register_and_login(client, "v03-collection-idempotency@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={
            "keyword": "Agent",
            "city": "杭州",
            "limit": 20,
            "idempotency_key": "batch-key-0001",
            "extension_version": "0.1.0",
        },
    )
    assert first_session.status_code == 200, first_session.text
    session = first_session.json()
    assert session["adapter_name"] == "boss-browser"
    assert session["adapter_enabled_snapshot"] is True
    assert session["extension_version"] == "0.1.0"
    assert session["page_limit"] == settings.boss_collection_page_limit

    reused_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={
            "keyword": "Agent",
            "city": "杭州",
            "limit": 20,
            "idempotency_key": "batch-key-0001",
            "extension_version": "0.1.0",
        },
    )
    assert reused_session.status_code == 200
    assert reused_session.json()["id"] == session["id"]

    submit = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "idempotency_key": "batch-key-0001",
            "extension_version": "0.1.0",
            "jobs": [
                {
                    "title": "AI Agent 平台工程师",
                    "company": "幂等测试公司",
                    "location": "杭州",
                    "tags": ["Agent", "Python"],
                    "description": "负责 Agent 平台、RAG 和 Python 后端开发。",
                    "source_job_id": "boss-source-1",
                }
            ],
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["created"] == 1

    duplicate_submit = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "idempotency_key": "batch-key-0001",
            "jobs": [],
        },
    )
    assert duplicate_submit.status_code == 200
    assert duplicate_submit.json()["created"] == 1

    source_duplicate_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "city": "杭州", "limit": 20},
    ).json()
    source_duplicate = client.post(
        f"/api/v1/job-collections/sessions/{source_duplicate_session['id']}/jobs",
        json={
            "collection_token": source_duplicate_session["collection_token"],
            "jobs": [
                {
                    "title": "改名后的 Agent 岗位",
                    "company": "不同公司名",
                    "location": "上海",
                    "tags": ["Agent"],
                    "description": "同一个 Boss 来源岗位，来源 ID 优先去重。",
                    "source_job_id": "boss-source-1",
                }
            ],
        },
    )
    assert source_duplicate.status_code == 200, source_duplicate.text
    assert source_duplicate.json()["duplicated"] == 1

    fallback_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "city": "杭州", "limit": 20},
    ).json()
    fallback_submit = client.post(
        f"/api/v1/job-collections/sessions/{fallback_session['id']}/jobs",
        json={
            "collection_token": fallback_session["collection_token"],
            "jobs": [
                {
                    "title": "AI Agent 后端开发",
                    "company": "指纹测试公司",
                    "location": "杭州",
                    "tags": ["Agent", "FastAPI"],
                    "description": "负责 Agent、FastAPI、RAG 和后端平台开发。",
                }
            ],
        },
    )
    assert fallback_submit.status_code == 200, fallback_submit.text
    assert fallback_submit.json()["created"] == 1

    fallback_duplicate_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "city": "杭州", "limit": 20},
    ).json()
    fallback_duplicate = client.post(
        f"/api/v1/job-collections/sessions/{fallback_duplicate_session['id']}/jobs",
        json={
            "collection_token": fallback_duplicate_session["collection_token"],
            "jobs": [
                {
                    "title": "AI Agent 后端开发",
                    "company": "指纹测试公司",
                    "location": "杭州",
                    "tags": ["Agent", "FastAPI"],
                    "description": "负责 Agent、FastAPI、RAG 和后端平台开发。",
                }
            ],
        },
    )
    assert fallback_duplicate.status_code == 200, fallback_duplicate.text
    assert fallback_duplicate.json()["duplicated"] == 1

    jobs_before_failure = client.get("/api/v1/jobs", headers=headers).json()
    failure_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "city": "杭州", "limit": 20},
    ).json()
    failure = client.post(
        f"/api/v1/job-collections/sessions/{failure_session['id']}/jobs",
        json={
            "collection_token": failure_session["collection_token"],
            "status": "SOURCE_CHANGED",
            "error_code": "SOURCE_CHANGED",
            "error_message": "页面结构变化",
            "jobs": [
                {
                    "title": "不应写入的 Agent 岗位",
                    "company": "异常测试公司",
                    "location": "杭州",
                    "tags": ["Agent"],
                    "description": "异常采集状态下不能写入。",
                }
            ],
        },
    )
    assert failure.status_code == 200, failure.text
    assert failure.json()["created"] == 0
    assert client.get("/api/v1/jobs", headers=headers).json() == jobs_before_failure


def test_collection_adapter_guards(monkeypatch, client: TestClient) -> None:
    token = _register_and_login(client, "v03-adapter-guards@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(settings, "boss_adapter_enabled", False)
    disabled_status = client.get("/api/v1/job-collections/adapter-status", headers=headers)
    assert disabled_status.status_code == 200
    assert disabled_status.json()["enabled"] is False
    disabled_create = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "limit": 10},
    )
    assert disabled_create.status_code == 503

    monkeypatch.setattr(settings, "boss_adapter_enabled", True)
    monkeypatch.setattr(settings, "boss_adapter_min_extension_version", "0.2.0")
    old_extension = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "limit": 10, "extension_version": "0.1.0"},
    )
    assert old_extension.status_code == 426

    monkeypatch.setattr(settings, "boss_adapter_min_extension_version", "0.1.0")
    monkeypatch.setattr(settings, "boss_collection_rate_limit_max_sessions", 1)
    first = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "limit": 10},
    )
    assert first.status_code == 200
    limited = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "limit": 10},
    )
    assert limited.status_code == 429
