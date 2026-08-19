from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_v01_account_config_resume import _register_and_login
from tests.test_v01_account_config_resume import client as client
from tests.test_v01_job_evaluation import _create_job_for_user, _setup_profile_and_resume


def _create_pool_job(client: TestClient, token: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _create_job_for_user(client, token)
    add_to_pool = client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers)
    assert add_to_pool.status_code == 200, add_to_pool.text
    return job_id


def test_interview_runs_from_job_pool_to_report(client: TestClient) -> None:
    token = _register_and_login(client, "interview-flow@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_pool_job(client, token)

    evaluation = client.post(f"/api/v1/jobs/{job_id}/evaluations", headers=headers, json={})
    assert evaluation.status_code == 200, evaluation.text

    start = client.post(
        "/api/v1/interviews",
        headers=headers,
        json={"job_id": job_id, "max_questions": 2},
    )
    assert start.status_code == 200, start.text
    session = start.json()
    assert session["job_id"] == job_id
    assert session["status"] == "running"
    assert session["retrieval_mode"] == "pgvector-fallback-v1"
    assert session["current_turn"]["question_type"] == "opening"
    assert "自我介绍" in session["current_turn"]["question_text"]
    assert session["current_turn"]["question_bank_item_external_id"] is None

    intro = client.post(
        f"/api/v1/interviews/{session['id']}/answers",
        headers=headers,
        json={"answer_text": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert intro.status_code == 200, intro.text
    after_intro = intro.json()
    assert after_intro["turns"][0]["question_type"] == "opening"
    assert after_intro["turns"][0]["score"] is None
    assert after_intro["current_turn"]["turn_index"] == 2

    first_answer = client.post(
        f"/api/v1/interviews/{session['id']}/answers",
        headers=headers,
        json={
            "answer_text": (
                "我会把题目、参考答案、评分 rubric、技能标签和来源结构化入库，"
                "用 pgvector 做 Top-K 检索，再按 JD 和简历过滤，评分时引用用户回答证据。"
            )
        },
    )
    assert first_answer.status_code == 200, first_answer.text
    after_first = first_answer.json()
    assert after_first["turns"][1]["score"] is not None
    assert after_first["turns"][1]["evidence"]
    assert after_first["current_turn"] is not None

    second_answer = client.post(
        f"/api/v1/interviews/{session['id']}/answers",
        headers=headers,
        json={
            "answer_text": (
                "LangGraph 可以把加载上下文、检索、选题、等待回答、评分和报告拆成节点，"
                "通过 checkpoint 恢复，并用代码限制追问次数和题目数量。"
            )
        },
    )
    assert second_answer.status_code == 200, second_answer.text
    after_second = second_answer.json()
    assert after_second["status"] == "running"
    assert after_second["current_turn"]["question_type"] == "closing"

    final_answer = client.post(
        f"/api/v1/interviews/{session['id']}/answers",
        headers=headers,
        json={"answer_text": "我想了解团队对项目质量、成长空间和协作方式的要求。"},
    )
    assert final_answer.status_code == 200, final_answer.text
    completed = final_answer.json()
    assert completed["status"] == "completed"
    assert completed["report"]["total_score"] > 0
    assert completed["report"]["evidence"]
    assert completed["report"]["evidence"][0]["source_question_id"]
    assert completed["main_questions_answered"] == 2

    history = client.get("/api/v1/interviews/history", headers=headers)
    assert history.status_code == 200, history.text
    assert len(history.json()) == 1
    assert history.json()[0]["job_id"] == job_id
    assert history.json()[0]["job_title"] == "AI Agent 开发实习生"
    assert history.json()[0]["question_count"] == 2
    assert history.json()[0]["total_score"] > 0

    pool = client.get("/api/v1/jobs/pool", headers=headers)
    assert pool.status_code == 200
    assert pool.json()[0]["has_interviewed"] is True


def test_interview_can_follow_up_on_weak_answer(client: TestClient) -> None:
    token = _register_and_login(client, "interview-followup@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_pool_job(client, token)

    start = client.post(
        "/api/v1/interviews",
        headers=headers,
        json={"job_id": job_id, "max_questions": 2},
    ).json()
    intro = client.post(
        f"/api/v1/interviews/{start['id']}/answers",
        headers=headers,
        json={"answer_text": "我主要负责后端接口、检索和数据处理。"},
    )
    assert intro.status_code == 200, intro.text

    response = client.post(
        f"/api/v1/interviews/{start['id']}/answers",
        headers=headers,
        json={"answer_text": "不太清楚。"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "running"
    assert body["current_turn"]["is_followup"] is True
    assert body["turns"][1]["score"] < 60


def test_interview_history_omits_sessions_without_answers(client: TestClient) -> None:
    token = _register_and_login(client, "interview-empty-history@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_pool_job(client, token)

    start = client.post(
        "/api/v1/interviews",
        headers=headers,
        json={"job_id": job_id, "max_questions": 2},
    )
    assert start.status_code == 200, start.text

    history = client.get("/api/v1/interviews/history", headers=headers)
    assert history.status_code == 200
    assert history.json() == []

    pool = client.get("/api/v1/jobs/pool", headers=headers)
    assert pool.status_code == 200
    assert pool.json()[0]["has_interviewed"] is False


def test_interview_requires_job_pool_and_default_resume(client: TestClient) -> None:
    token = _register_and_login(client, "interview-guard@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _create_job_for_user(client, token)

    no_pool = client.post(
        "/api/v1/interviews",
        headers=headers,
        json={"job_id": job_id, "max_questions": 2},
    )
    assert no_pool.status_code == 422
    assert "岗位池" in no_pool.json()["error"]["message"]

    add_to_pool = client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers)
    assert add_to_pool.status_code == 200
    no_resume = client.post(
        "/api/v1/interviews",
        headers=headers,
        json={"job_id": job_id, "max_questions": 2},
    )
    assert no_resume.status_code == 422
    assert "默认简历" in no_resume.json()["error"]["message"]


def test_user_cannot_access_other_users_interview(client: TestClient) -> None:
    token_a = _register_and_login(client, "interview-owner@example.com")
    token_b = _register_and_login(client, "interview-other@example.com")
    _setup_profile_and_resume(client, token_a)
    _setup_profile_and_resume(client, token_b)
    job_id = _create_pool_job(client, token_a)

    session = client.post(
        "/api/v1/interviews",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"job_id": job_id, "max_questions": 2},
    ).json()

    forbidden = client.get(
        f"/api/v1/interviews/{session['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden.status_code == 404


def test_interview_history_can_be_deleted_in_batch(client: TestClient) -> None:
    token = _register_and_login(client, "interview-history-delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    session_ids = []

    for index in range(2):
        job_id = _create_pool_job(client, token)
        start = client.post(
            "/api/v1/interviews",
            headers=headers,
            json={"job_id": job_id, "max_questions": 1},
        ).json()
        intro = client.post(
            f"/api/v1/interviews/{start['id']}/answers",
            headers=headers,
            json={"answer_text": f"第 {index} 次自我介绍，包含后端和检索经历。"},
        )
        assert intro.status_code == 200, intro.text
        answer = client.post(
            f"/api/v1/interviews/{start['id']}/answers",
            headers=headers,
            json={"answer_text": f"第 {index} 次回答，包含检索、评分、证据和 LangGraph。"},
        )
        assert answer.status_code == 200, answer.text
        closing = client.post(
            f"/api/v1/interviews/{start['id']}/answers",
            headers=headers,
            json={"answer_text": f"第 {index} 次反问，想了解团队更看重什么。"},
        )
        assert closing.status_code == 200, closing.text
        session_ids.append(start["id"])

    history = client.get("/api/v1/interviews/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 2

    delete_response = client.request(
        "DELETE",
        "/api/v1/interviews/history",
        headers=headers,
        json={"session_ids": session_ids},
    )
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["deleted_count"] == 2

    history_after = client.get("/api/v1/interviews/history", headers=headers)
    assert history_after.status_code == 200
    assert history_after.json() == []
