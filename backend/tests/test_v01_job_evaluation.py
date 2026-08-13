from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_v01_account_config_resume import _register_and_login
from tests.test_v01_account_config_resume import client as client


def _create_job_for_user(
    client: TestClient,
    token: str,
    *,
    title: str = "AI Agent 开发实习生",
    company: str = "未来工具链科技",
    description: str = "负责 Python、FastAPI、RAG 和 AI Agent 求职工具开发。",
    salary: str = "200-300元/天",
    location: str = "济南",
    tags: list[str] | None = None,
) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "city": location, "limit": 20},
    ).json()
    submit_response = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "salary": salary,
                    "tags": tags if tags is not None else ["Python", "FastAPI", "Agent"],
                    "description": description,
                    "job_url": f"https://www.zhipin.com/job_detail/{company}.html",
                }
            ],
        },
    )
    assert submit_response.status_code == 200, submit_response.text
    jobs = client.get("/api/v1/jobs", headers=headers).json()
    assert jobs
    return jobs[0]["id"]


def _setup_profile_and_resume(
    client: TestClient,
    token: str,
    *,
    deal_breakers: str = "",
    resume_text: str = "Python FastAPI RAG Agent 项目，使用 SQL、Redis、Docker 做过后端开发。",
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    profile = client.put(
        "/api/v1/profile",
        headers=headers,
        json={
            "target_role": "Agent 开发实习生",
            "salary_min": 180,
            "salary_max": 320,
            "cities": "济南,杭州",
            "work_type": "internship",
            "deal_breakers": deal_breakers,
        },
    )
    assert profile.status_code == 200, profile.text
    resume = client.post(
        "/api/v1/resumes/upload",
        headers=headers,
        files={
            "file": (
                "resume.md",
                resume_text.encode(),
                "text/markdown",
            )
        },
    )
    assert resume.status_code == 201, resume.text


def test_job_evaluation_creates_framework_report(client: TestClient) -> None:
    token = _register_and_login(client, "eval-normal@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(client, token)

    response = client.post(f"/api/v1/jobs/{job_id}/evaluations", headers=headers, json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == job_id
    assert body["framework_version"] == "v1"
    assert body["final_score"] >= 70
    assert body["recommendation"] in {"可投递", "强烈投递"}
    assert body["dimensions"]["skill_match"]["weight"] == 0.3
    assert body["dimensions"]["experience_match"]["weight"] == 0.25
    assert body["resume_focus_suggestions"]
    assert body["evidence"]

    history = client.get(f"/api/v1/jobs/{job_id}/evaluations", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_job_evaluation_dealbreaker_caps_score(client: TestClient) -> None:
    token = _register_and_login(client, "eval-dealbreaker@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token, deal_breakers="外包")
    job_id = _create_job_for_user(
        client,
        token,
        title="AI Agent 外包实习生",
        description="负责 Python 和 Agent 开发，但岗位为外包项目，节奏较快。",
    )

    response = client.post(f"/api/v1/jobs/{job_id}/evaluations", headers=headers, json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["raw_weighted_score"] > 30
    assert body["final_score"] <= 30
    assert "外包" in body["dealbreakers_hit"]
    assert body["recommendation"] == "不建议"


def test_job_evaluation_splits_required_and_preferred_jd_skills(client: TestClient) -> None:
    token = _register_and_login(client, "eval-jd-requirements@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(
        client,
        token,
        resume_text="Java Spring Boot SQL 后端项目，负责接口开发、数据库设计和 Docker 部署。",
    )
    job_id = _create_job_for_user(
        client,
        token,
        title="Java 后端开发实习生",
        description=(
            "岗位要求：熟悉 Java、Spring Boot、SQL，能够独立完成后端接口开发。"
            "有 AI Agent、RAG 项目经验优先。"
        ),
        tags=[],
    )

    response = client.post(f"/api/v1/jobs/{job_id}/evaluations", headers=headers, json={})

    assert response.status_code == 200, response.text
    body = response.json()
    requirements = body["jd_requirements"]
    assert {"Java", "Spring Boot", "SQL"}.issubset(set(requirements["required_skills"]))
    assert {"Agent", "RAG"}.issubset(set(requirements["preferred_skills"]))
    assert {"Java", "Spring Boot", "SQL"}.issubset(
        set(requirements["matched_required_skills"])
    )
    assert {"Agent", "RAG"}.issubset(set(requirements["missing_preferred_skills"]))
    assert any("JD 必备技能" in item for item in body["resume_focus_suggestions"])
    assert any("加分项" in item for item in body["risks_and_gaps"])


def test_job_evaluation_requires_default_resume(client: TestClient) -> None:
    token = _register_and_login(client, "eval-no-resume@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _create_job_for_user(client, token)

    response = client.post(f"/api/v1/jobs/{job_id}/evaluations", headers=headers, json={})

    assert response.status_code == 422
    assert "默认简历" in response.json()["error"]["message"]


def test_user_cannot_evaluate_other_users_job(client: TestClient) -> None:
    token_a = _register_and_login(client, "eval-owner@example.com")
    token_b = _register_and_login(client, "eval-other@example.com")
    _setup_profile_and_resume(client, token_a)
    _setup_profile_and_resume(client, token_b)
    job_id = _create_job_for_user(client, token_a)

    response = client.post(
        f"/api/v1/jobs/{job_id}/evaluations",
        headers={"Authorization": f"Bearer {token_b}"},
        json={},
    )

    assert response.status_code == 404
