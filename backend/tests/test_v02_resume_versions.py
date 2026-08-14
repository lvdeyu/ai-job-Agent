from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_v01_account_config_resume import _register_and_login
from tests.test_v01_account_config_resume import client as client
from tests.test_v01_job_evaluation import _create_job_for_user, _setup_profile_and_resume


def test_job_pool_uploaded_resume_takes_priority_for_evaluation(client: TestClient) -> None:
    token = _register_and_login(client, "v02-job-upload-priority@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(
        client,
        token,
        resume_text="Python 后端项目，负责接口开发。",
    )
    job_id = _create_job_for_user(
        client,
        token,
        description="岗位要求：熟悉 Python、FastAPI、RAG 和 AI Agent，负责求职 Agent 工具开发。",
    )
    pool_response = client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers)
    assert pool_response.status_code == 200, pool_response.text

    baseline = client.post(f"/api/v1/jobs/{job_id}/evaluations", headers=headers, json={})
    assert baseline.status_code == 200, baseline.text
    baseline_body = baseline.json()
    assert baseline_body["resume_source_type"] == "uploaded"

    upload_response = client.post(
        f"/api/v1/resumes/jobs/{job_id}/upload",
        headers=headers,
        files={
            "file": (
                "agent-job-resume.md",
                (
                    "Python FastAPI RAG AI Agent 项目，使用 SQL、Redis、Docker 完成后端开发，"
                    "负责工具调用、检索增强和求职评测链路。"
                ).encode(),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 201, upload_response.text
    uploaded = upload_response.json()
    assert uploaded["source_type"] == "job_upload"
    assert uploaded["job_id"] == job_id

    current = client.post(f"/api/v1/jobs/{job_id}/evaluations", headers=headers, json={})
    assert current.status_code == 200, current.text
    current_body = current.json()
    assert current_body["resume_version_id"] == uploaded["id"]
    assert current_body["resume_source_type"] == "job_upload"
    assert current_body["final_score"] > baseline_body["final_score"]
    assert any("简历版本" in item for item in current_body["evidence"])

    resumes = client.get("/api/v1/resumes", headers=headers).json()
    default_resumes = [resume for resume in resumes if resume["is_default"]]
    assert len(default_resumes) == 1
    assert default_resumes[0]["versions"][0]["source_type"] == "uploaded"


def test_job_resume_upload_requires_owned_pool_job(client: TestClient) -> None:
    token_a = _register_and_login(client, "v02-upload-owner@example.com")
    token_b = _register_and_login(client, "v02-upload-other@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    _setup_profile_and_resume(client, token_a)
    _setup_profile_and_resume(client, token_b)
    job_id = _create_job_for_user(client, token_a)

    not_in_pool = client.post(
        f"/api/v1/resumes/jobs/{job_id}/upload",
        headers=headers_a,
        files={"file": ("resume.md", b"Python FastAPI Agent", "text/markdown")},
    )
    assert not_in_pool.status_code == 422
    assert "岗位池" in not_in_pool.json()["error"]["message"]

    client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers_a)
    cross_user = client.post(
        f"/api/v1/resumes/jobs/{job_id}/upload",
        headers=headers_b,
        files={"file": ("resume.md", b"Python FastAPI Agent", "text/markdown")},
    )
    assert cross_user.status_code == 404


def test_job_specific_resume_version_can_be_edited_and_reevaluated(
    client: TestClient,
) -> None:
    token = _register_and_login(client, "v02-resume-version@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(
        client,
        token,
        resume_text="Python 后端项目，负责接口开发。",
    )
    job_id = _create_job_for_user(
        client,
        token,
        description="岗位要求：熟悉 Python、FastAPI、RAG 和 AI Agent，负责求职 Agent 工具开发。",
    )
    pool_response = client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers)
    assert pool_response.status_code == 200, pool_response.text

    resumes_before = client.get("/api/v1/resumes", headers=headers).json()
    source_version = resumes_before[0]["versions"][0]
    baseline = client.post(
        f"/api/v1/jobs/{job_id}/evaluations",
        headers=headers,
        json={"resume_version_id": source_version["id"]},
    )
    assert baseline.status_code == 200, baseline.text

    copy_response = client.post(
        "/api/v1/resumes/versions/job-specific",
        headers=headers,
        json={
            "job_id": job_id,
            "source_resume_version_id": source_version["id"],
            "title": "Agent 岗位专属简历 v2",
        },
    )
    assert copy_response.status_code == 201, copy_response.text
    copied = copy_response.json()
    assert copied["source_type"] == "job_copy"
    assert copied["source_version_id"] == source_version["id"]
    assert copied["job_id"] == job_id
    assert copied["version_no"] == 2
    assert copied["extracted_text"] == source_version["extracted_text"]

    edited_text = (
        "Python FastAPI RAG AI Agent 项目，使用 SQL、Redis、Docker 完成后端开发，"
        "负责工具调用、检索增强和求职评测链路。"
    )
    edit_response = client.patch(
        f"/api/v1/resumes/versions/{copied['id']}",
        headers=headers,
        json={"title": "Agent 岗位专属简历 v2.1", "extracted_text": edited_text},
    )
    assert edit_response.status_code == 200, edit_response.text
    edited = edit_response.json()
    assert edited["title"] == "Agent 岗位专属简历 v2.1"
    assert "FastAPI RAG AI Agent" in edited["extracted_text"]
    assert edited["updated_at"] is not None

    resumes_after = client.get("/api/v1/resumes", headers=headers).json()
    original_version = next(
        version
        for resume in resumes_after
        for version in resume["versions"]
        if version["id"] == source_version["id"]
    )
    assert original_version["extracted_text"] == source_version["extracted_text"]

    reevaluation = client.post(
        f"/api/v1/jobs/{job_id}/evaluations",
        headers=headers,
        json={"resume_version_id": copied["id"]},
    )
    assert reevaluation.status_code == 200, reevaluation.text
    current_body = reevaluation.json()
    baseline_body = baseline.json()
    assert current_body["resume_version_id"] == copied["id"]
    assert current_body["resume_title"] == "Agent 岗位专属简历 v2.1"
    assert current_body["output_schema_version"] == "evaluation-json-v1"
    assert current_body["final_score"] > baseline_body["final_score"]
    assert any("简历版本" in item for item in current_body["evidence"])

    history = client.get(f"/api/v1/jobs/{job_id}/evaluations", headers=headers)
    assert history.status_code == 200
    bodies = history.json()
    assert len(bodies) == 2
    assert {item["resume_version_id"] for item in bodies} == {source_version["id"], copied["id"]}


def test_only_job_specific_resume_versions_are_editable(client: TestClient) -> None:
    token = _register_and_login(client, "v02-original-protected@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    source_version = client.get("/api/v1/resumes", headers=headers).json()[0]["versions"][0]

    response = client.patch(
        f"/api/v1/resumes/versions/{source_version['id']}",
        headers=headers,
        json={"title": "不应该覆盖原始版本", "extracted_text": "覆盖原文"},
    )

    assert response.status_code == 422
    assert "原始上传版本不会被覆盖" in response.json()["error"]["message"]


def test_user_cannot_copy_or_edit_other_users_resume_version(client: TestClient) -> None:
    token_a = _register_and_login(client, "v02-owner@example.com")
    token_b = _register_and_login(client, "v02-other@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    _setup_profile_and_resume(client, token_a)
    _setup_profile_and_resume(client, token_b)
    job_id = _create_job_for_user(client, token_b)
    pool_response = client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers_b)
    assert pool_response.status_code == 200, pool_response.text
    owner_version = client.get("/api/v1/resumes", headers=headers_a).json()[0]["versions"][0]

    copy_response = client.post(
        "/api/v1/resumes/versions/job-specific",
        headers=headers_b,
        json={"job_id": job_id, "source_resume_version_id": owner_version["id"]},
    )

    assert copy_response.status_code == 404

    edit_response = client.patch(
        f"/api/v1/resumes/versions/{owner_version['id']}",
        headers=headers_b,
        json={"title": "越权编辑", "extracted_text": "越权内容"},
    )
    assert edit_response.status_code == 404
