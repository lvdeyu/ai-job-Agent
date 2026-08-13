from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.boss_search import build_boss_search_url
from tests.test_v01_account_config_resume import _register_and_login
from tests.test_v01_account_config_resume import client as client


def test_boss_search_url_uses_stable_city_code_and_keyword_for_internship() -> None:
    url = build_boss_search_url("运营", "济南", "internship")

    assert "https://www.zhipin.com/web/geek/jobs?" in url
    assert "query=%E8%BF%90%E8%90%A5" in url
    assert "%E5%AE%9E%E4%B9%A0" not in url
    assert "city=101120100" in url
    assert "jobType=intern" not in url


def test_boss_search_url_omits_unknown_city_instead_of_sending_raw_text() -> None:
    url = build_boss_search_url("AI 应用开发", "未知城市", None)

    assert "query=AI+%E5%BA%94%E7%94%A8%E5%BC%80%E5%8F%91" in url
    assert "city=%E6%9C%AA%E7%9F%A5%E5%9F%8E%E5%B8%82" not in url


def test_create_collection_session_and_submit_jobs(client: TestClient) -> None:
    token = _register_and_login(client, "collector@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    session_response = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent 开发实习", "city": "杭州", "work_type": "internship", "limit": 20},
    )
    assert session_response.status_code == 200, session_response.text
    session = session_response.json()
    assert "zhipin.com" in session["boss_search_url"]

    submit_response = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": "AI Agent 开发实习生",
                    "company": "未来工具链科技",
                    "location": "杭州",
                    "salary": "200-300元/天",
                    "tags": ["Python", "Agent"],
                    "job_url": "https://www.zhipin.com/job_detail/demo.html",
                }
            ],
        },
    )
    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["created"] == 1

    jobs_response = client.get("/api/v1/jobs", headers=headers)
    assert jobs_response.status_code == 200
    assert jobs_response.json()[0]["title"] == "AI Agent 开发实习生"


def test_collected_jobs_are_isolated_by_user(client: TestClient) -> None:
    token_a = _register_and_login(client, "collector-a@example.com")
    token_b = _register_and_login(client, "collector-b@example.com")

    session = client.post(
        "/api/v1/job-collections/sessions",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"keyword": "后端实习", "limit": 20},
    ).json()
    client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [{"title": "Java 后端实习生", "company": "A 公司"}],
        },
    )

    jobs_b = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {token_b}"})
    assert jobs_b.status_code == 200
    assert jobs_b.json() == []


def test_collected_jobs_are_filtered_by_keyword_relevance(client: TestClient) -> None:
    token = _register_and_login(client, "keyword-filter@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "python", "city": "济南", "work_type": "internship", "limit": 20},
    ).json()
    submit_response = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": "机械设计实习生",
                    "company": "制造业公司",
                    "location": "济南",
                    "tags": ["本科", "在校"],
                    "description": "负责机械图纸整理。",
                },
                {
                    "title": "Python 开发实习生",
                    "company": "AI 工具链公司",
                    "location": "济南",
                    "tags": ["Python", "FastAPI"],
                    "description": "参与 Python 后端和 Agent 工具开发。",
                },
            ],
        },
    )

    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["created"] == 1
    assert submit_response.json()["filtered"] == 1

    jobs = client.get("/api/v1/jobs", headers=headers).json()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Python 开发实习生"


def test_keyword_and_work_type_are_filtered_separately(client: TestClient) -> None:
    token = _register_and_login(client, "agent-work-type@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "city": "济南", "work_type": "internship", "limit": 20},
    ).json()
    assert "%E5%AE%9E%E4%B9%A0" not in session["boss_search_url"]

    submit_response = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": "AI/AI Infra/AI 应用/Agent",
                    "company": "华为技术有限公司",
                    "location": "济南",
                    "tags": ["在校/应届", "本科"],
                    "description": "AI 应用工程师方向，包含 Agent 技术、模型评测和 AI 算法。",
                },
                {
                    "title": "AI 应用工程师（AI/Agent/skill）",
                    "company": "餐饮管理公司",
                    "location": "济南",
                    "tags": ["3-5年", "本科"],
                    "description": "负责 AI Agent 应用研发。",
                },
                {
                    "title": "机械设计实习生",
                    "company": "制造业公司",
                    "location": "济南",
                    "tags": ["在校/应届", "本科"],
                    "description": "负责机械设计。",
                },
            ],
        },
    )

    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["created"] == 1
    assert submit_response.json()["filtered"] == 2

    jobs = client.get("/api/v1/jobs", headers=headers).json()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "AI/AI Infra/AI 应用/Agent"


def test_relevant_agent_job_without_work_type_marker_is_kept(client: TestClient) -> None:
    token = _register_and_login(client, "agent-unknown-work-type@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "city": "济南", "work_type": "internship", "limit": 20},
    ).json()

    submit_response = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": "AI 应用开发工程师",
                    "company": "智能工具链公司",
                    "location": "济南",
                    "tags": ["本科", "Python"],
                    "description": "负责大模型应用、智能体工作流和 AI Agent 工具开发。",
                }
            ],
        },
    )

    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["created"] == 1
    assert submit_response.json()["filtered"] == 0


def test_agent_keyword_matches_chinese_aliases(client: TestClient) -> None:
    token = _register_and_login(client, "agent-alias@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "Agent", "city": "济南", "limit": 20},
    ).json()

    submit_response = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": "大模型应用开发实习生",
                    "company": "AI 创新公司",
                    "location": "济南",
                    "tags": ["Python", "RAG"],
                    "description": "围绕智能体、工具调用和知识库问答开发求职助手。",
                }
            ],
        },
    )

    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["created"] == 1


def test_new_keyword_session_filters_previous_keyword_results(client: TestClient) -> None:
    token = _register_and_login(client, "java-session-isolation@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "java", "city": "济南", "work_type": "full_time", "limit": 20},
    ).json()

    submit_response = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": "AI Agent 产品实习生",
                    "company": "上一轮旧页面公司",
                    "location": "济南",
                    "tags": ["Agent", "RAG"],
                    "description": "负责智能体产品和 RAG 知识库，不涉及 Java。",
                },
                {
                    "title": "Java 后端开发工程师",
                    "company": "本次搜索公司",
                    "location": "济南",
                    "tags": ["Java", "Spring Boot"],
                    "description": "负责 Java 后端、Spring Boot 和数据库开发。",
                },
            ],
        },
    )

    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["created"] == 1
    assert submit_response.json()["filtered"] == 1

    jobs = client.get("/api/v1/jobs", headers=headers).json()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Java 后端开发工程师"


def test_java_keyword_rejects_ai_job_with_only_incidental_java_mention(client: TestClient) -> None:
    token = _register_and_login(client, "java-incidental-filter@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "java", "city": "济南", "work_type": "full_time", "limit": 20},
    ).json()

    submit_response = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": "企业AI落地负责人（FDE方向）",
                    "company": "美智医疗",
                    "location": "济南",
                    "salary": "10-15K",
                    "tags": ["1年以内", "学历不限"],
                    "description": (
                        "负责 Agent、RAG、Python、LLM 和 Prompt 工作流，偶尔对接 Java 系统。"
                    ),
                },
                {
                    "title": "后端开发工程师",
                    "company": "本次搜索公司",
                    "location": "济南",
                    "salary": "10-15K",
                    "tags": ["Java", "Spring Boot", "MySQL"],
                    "description": "负责 Java 后端、Spring Boot 和数据库开发。",
                },
            ],
        },
    )

    assert submit_response.status_code == 200, submit_response.text
    assert submit_response.json()["created"] == 1
    assert submit_response.json()["filtered"] == 1

    jobs = client.get("/api/v1/jobs", headers=headers).json()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "后端开发工程师"


def test_duplicate_jobs_are_attached_to_new_collection_session(client: TestClient) -> None:
    token = _register_and_login(client, "collection-history-duplicates@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "java", "city": "济南", "work_type": "full_time", "limit": 20},
    ).json()
    first_submit = client.post(
        f"/api/v1/job-collections/sessions/{first_session['id']}/jobs",
        json={
            "collection_token": first_session["collection_token"],
            "jobs": [
                {
                    "title": "Java 后端开发工程师",
                    "company": "重复公司",
                    "location": "济南",
                    "tags": ["Java", "Spring Boot"],
                    "description": "负责 Java 后端和 Spring Boot 开发。",
                }
            ],
        },
    )
    assert first_submit.status_code == 200, first_submit.text
    assert first_submit.json()["created"] == 1

    second_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "java", "city": "济南", "work_type": "full_time", "limit": 20},
    ).json()
    second_submit = client.post(
        f"/api/v1/job-collections/sessions/{second_session['id']}/jobs",
        json={
            "collection_token": second_session["collection_token"],
            "jobs": [
                {
                    "title": "Java 后端开发工程师",
                    "company": "重复公司",
                    "location": "济南",
                    "tags": ["Java", "Spring Boot"],
                    "description": "负责 Java 后端和 Spring Boot 开发。",
                },
                {
                    "title": "Java 初级开发工程师",
                    "company": "新增公司",
                    "location": "济南",
                    "tags": ["Java", "SQL"],
                    "description": "负责 Java 接口和 SQL 数据库开发。",
                },
            ],
        },
    )
    assert second_submit.status_code == 200, second_submit.text
    assert second_submit.json()["created"] == 1
    assert second_submit.json()["duplicated"] == 1

    session_detail = client.get(
        f"/api/v1/job-collections/sessions/{second_session['id']}",
        headers=headers,
    )
    assert session_detail.status_code == 200, session_detail.text
    body = session_detail.json()
    assert body["created_count"] == 1
    assert body["duplicated_count"] == 1
    assert [job["title"] for job in body["jobs"]] == [
        "Java 后端开发工程师",
        "Java 初级开发工程师",
    ]


def test_collection_history_is_paginated_and_sorted_by_time(client: TestClient) -> None:
    token = _register_and_login(client, "collection-history-page@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for index in range(12):
        session = client.post(
            "/api/v1/job-collections/sessions",
            headers=headers,
            json={"keyword": f"java {index}", "city": "济南", "limit": 10},
        ).json()
        submit = client.post(
            f"/api/v1/job-collections/sessions/{session['id']}/jobs",
            json={
                "collection_token": session["collection_token"],
                "jobs": [
                    {
                        "title": f"Java 开发工程师 {index}",
                        "company": f"公司 {index}",
                        "location": "济南",
                        "tags": ["Java"],
                        "description": "负责 Java 开发。",
                    }
                ],
            },
        )
        assert submit.status_code == 200, submit.text

    history = client.get(
        "/api/v1/job-collections/sessions?page=1&page_size=10",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    body = history.json()
    assert body["total"] == 12
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert len(body["items"]) == 10
    assert body["items"][0]["keyword"] == "java 11"
    assert body["items"][0]["job_count"] == 1

    second_page = client.get(
        "/api/v1/job-collections/sessions?page=2&page_size=10",
        headers=headers,
    )
    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 2


def test_collection_history_can_be_deleted_without_deleting_jobs(client: TestClient) -> None:
    token = _register_and_login(client, "collection-history-delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "java", "city": "济南", "work_type": "full_time", "limit": 10},
    ).json()
    submit = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": "Java 后端开发工程师",
                    "company": "删除历史测试公司",
                    "location": "济南",
                    "tags": ["Java", "Spring Boot"],
                    "description": "负责 Java 后端开发。",
                }
            ],
        },
    )
    assert submit.status_code == 200, submit.text

    delete_response = client.delete(
        f"/api/v1/job-collections/sessions/{session['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    deleted_detail = client.get(
        f"/api/v1/job-collections/sessions/{session['id']}",
        headers=headers,
    )
    assert deleted_detail.status_code == 404

    history = client.get("/api/v1/job-collections/sessions", headers=headers)
    assert history.status_code == 200
    assert all(item["id"] != session["id"] for item in history.json()["items"])

    jobs = client.get("/api/v1/jobs", headers=headers)
    assert jobs.status_code == 200
    assert [job["title"] for job in jobs.json()] == ["Java 后端开发工程师"]


def test_collection_history_can_be_deleted_in_batch(client: TestClient) -> None:
    token_a = _register_and_login(client, "collection-history-batch-delete-a@example.com")
    token_b = _register_and_login(client, "collection-history-batch-delete-b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    owned_session_ids = []
    for index in range(2):
        session = client.post(
            "/api/v1/job-collections/sessions",
            headers=headers_a,
            json={"keyword": "java", "city": "济南", "work_type": "full_time", "limit": 10},
        ).json()
        owned_session_ids.append(session["id"])
        submit = client.post(
            f"/api/v1/job-collections/sessions/{session['id']}/jobs",
            json={
                "collection_token": session["collection_token"],
                "jobs": [
                    {
                        "title": f"Java 后端开发工程师 {index}",
                        "company": f"批量删除测试公司 {index}",
                        "location": "济南",
                        "tags": ["Java", "Spring Boot"],
                        "description": "负责 Java 后端开发。",
                    }
                ],
            },
        )
        assert submit.status_code == 200, submit.text

    other_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers_b,
        json={"keyword": "java", "city": "济南", "limit": 10},
    ).json()

    delete_response = client.request(
        "DELETE",
        "/api/v1/job-collections/sessions",
        headers=headers_a,
        json={"session_ids": [*owned_session_ids, other_session["id"], "missing-session"]},
    )
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["deleted_count"] == 2

    history_a = client.get("/api/v1/job-collections/sessions", headers=headers_a)
    assert history_a.status_code == 200
    assert history_a.json()["items"] == []

    history_b = client.get("/api/v1/job-collections/sessions", headers=headers_b)
    assert history_b.status_code == 200
    assert [item["id"] for item in history_b.json()["items"]] == [other_session["id"]]

    jobs_a = client.get("/api/v1/jobs", headers=headers_a)
    assert jobs_a.status_code == 200
    assert sorted(job["title"] for job in jobs_a.json()) == [
        "Java 后端开发工程师 0",
        "Java 后端开发工程师 1",
    ]


def test_collection_history_delete_is_user_scoped(client: TestClient) -> None:
    token_a = _register_and_login(client, "collection-history-delete-a@example.com")
    token_b = _register_and_login(client, "collection-history-delete-b@example.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers_a,
        json={"keyword": "python", "city": "杭州", "limit": 10},
    ).json()

    delete_response = client.delete(
        f"/api/v1/job-collections/sessions/{session['id']}",
        headers=headers_b,
    )
    assert delete_response.status_code == 404

    owner_detail = client.get(
        f"/api/v1/job-collections/sessions/{session['id']}",
        headers=headers_a,
    )
    assert owner_detail.status_code == 200


def test_job_can_be_added_to_pool_and_keeps_pool_marker_on_duplicate_search(
    client: TestClient,
) -> None:
    token = _register_and_login(client, "job-pool@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "java", "city": "济南", "work_type": "full_time", "limit": 10},
    ).json()
    first_submit = client.post(
        f"/api/v1/job-collections/sessions/{first_session['id']}/jobs",
        json={
            "collection_token": first_session["collection_token"],
            "jobs": [
                {
                    "title": "Java 后端开发工程师",
                    "company": "岗位池测试公司",
                    "location": "济南",
                    "tags": ["Java", "Spring Boot"],
                    "description": "负责 Java 后端、Spring Boot 和数据库开发。",
                    "job_url": "https://www.zhipin.com/job_detail/pool-demo.html",
                }
            ],
        },
    )
    assert first_submit.status_code == 200, first_submit.text
    job = client.get("/api/v1/jobs", headers=headers).json()[0]
    assert job["is_in_pool"] is False

    add_to_pool = client.post(f"/api/v1/jobs/{job['id']}/pool", headers=headers)
    assert add_to_pool.status_code == 200, add_to_pool.text
    assert add_to_pool.json()["is_in_pool"] is True

    idempotent_add = client.post(f"/api/v1/jobs/{job['id']}/pool", headers=headers)
    assert idempotent_add.status_code == 200
    assert idempotent_add.json()["is_in_pool"] is True

    pool = client.get("/api/v1/jobs/pool", headers=headers)
    assert pool.status_code == 200
    assert [item["id"] for item in pool.json()] == [job["id"]]

    second_session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": "java", "city": "济南", "work_type": "full_time", "limit": 10},
    ).json()
    second_submit = client.post(
        f"/api/v1/job-collections/sessions/{second_session['id']}/jobs",
        json={
            "collection_token": second_session["collection_token"],
            "jobs": [
                {
                    "title": "Java 后端开发工程师",
                    "company": "岗位池测试公司",
                    "location": "济南",
                    "tags": ["Java", "Spring Boot"],
                    "description": "负责 Java 后端、Spring Boot 和数据库开发。",
                    "job_url": "https://www.zhipin.com/job_detail/pool-demo.html",
                }
            ],
        },
    )
    assert second_submit.status_code == 200, second_submit.text
    assert second_submit.json()["duplicated"] == 1

    session_detail = client.get(
        f"/api/v1/job-collections/sessions/{second_session['id']}",
        headers=headers,
    )
    assert session_detail.status_code == 200
    assert session_detail.json()["jobs"][0]["is_in_pool"] is True


def test_job_pool_can_remove_jobs_in_batch_without_deleting_jobs(client: TestClient) -> None:
    token = _register_and_login(client, "job-pool-batch-remove@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    job_ids: list[str] = []

    for index in range(2):
        session = client.post(
            "/api/v1/job-collections/sessions",
            headers=headers,
            json={"keyword": "java", "city": "济南", "work_type": "full_time", "limit": 10},
        ).json()
        submit = client.post(
            f"/api/v1/job-collections/sessions/{session['id']}/jobs",
            json={
                "collection_token": session["collection_token"],
                "jobs": [
                    {
                        "title": f"Java 后端开发工程师 {index}",
                        "company": f"岗位池批量移除公司 {index}",
                        "location": "济南",
                        "tags": ["Java"],
                        "description": "负责 Java 后端开发。",
                    }
                ],
            },
        )
        assert submit.status_code == 200, submit.text
        jobs = client.get("/api/v1/jobs", headers=headers).json()
        job = next(job for job in jobs if job["title"] == f"Java 后端开发工程师 {index}")
        add_to_pool = client.post(f"/api/v1/jobs/{job['id']}/pool", headers=headers)
        assert add_to_pool.status_code == 200
        job_ids.append(job["id"])

    remove_response = client.request(
        "DELETE",
        "/api/v1/jobs/pool",
        headers=headers,
        json={"job_ids": job_ids},
    )
    assert remove_response.status_code == 200, remove_response.text
    assert remove_response.json()["removed_count"] == 2

    pool = client.get("/api/v1/jobs/pool", headers=headers)
    assert pool.status_code == 200
    assert pool.json() == []

    jobs = client.get("/api/v1/jobs", headers=headers)
    assert jobs.status_code == 200
    assert len(jobs.json()) == 2
