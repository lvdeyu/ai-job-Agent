from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.interview_graph import MAX_FOLLOWUP_DEPTH, route_next_step
from tests.test_v01_account_config_resume import _register_and_login
from tests.test_v01_account_config_resume import client as client
from tests.test_v01_job_evaluation import _create_job_for_user, _setup_profile_and_resume


def _create_pool_job(client: TestClient, token: str, **kwargs: object) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    job_id = _create_job_for_user(client, token, **kwargs)
    add_to_pool = client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers)
    assert add_to_pool.status_code == 200, add_to_pool.text
    return job_id


def _create_keyword_pool_job(
    client: TestClient,
    token: str,
    *,
    keyword: str,
    title: str,
    company: str,
    description: str,
    tags: list[str],
) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    session = client.post(
        "/api/v1/job-collections/sessions",
        headers=headers,
        json={"keyword": keyword, "city": "杭州", "limit": 20},
    ).json()
    submit = client.post(
        f"/api/v1/job-collections/sessions/{session['id']}/jobs",
        json={
            "collection_token": session["collection_token"],
            "jobs": [
                {
                    "title": title,
                    "company": company,
                    "location": "杭州",
                    "salary": "200-300元/天",
                    "tags": tags,
                    "description": description,
                    "job_url": f"https://www.zhipin.com/job_detail/{company}.html",
                }
            ],
        },
    )
    assert submit.status_code == 200, submit.text
    jobs = client.get("/api/v1/jobs", headers=headers).json()
    assert jobs
    job_id = next(job["id"] for job in jobs if job["title"] == title)
    add_to_pool = client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers)
    assert add_to_pool.status_code == 200, add_to_pool.text
    return job_id


def _upload_resume(client: TestClient, token: str, text: str) -> str:
    response = client.post(
        "/api/v1/resumes/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.md", text.encode(), "text/markdown")},
    )
    assert response.status_code == 201, response.text
    return response.json()["versions"][0]["id"]


def _start_interview(
    client: TestClient,
    headers: dict[str, str],
    job_id: str,
    *,
    max_questions: int = 3,
    resume_version_id: str | None = None,
) -> dict:
    payload: dict[str, object] = {"job_id": job_id, "max_questions": max_questions}
    if resume_version_id:
        payload["resume_version_id"] = resume_version_id
    start = client.post("/api/v1/interviews", headers=headers, json=payload)
    assert start.status_code == 200, start.text
    return start.json()


def _answer(client: TestClient, headers: dict[str, str], session_id: str, text: str) -> dict:
    response = client.post(
        f"/api/v1/interviews/{session_id}/answers",
        headers=headers,
        json={"answer_text": text},
    )
    assert response.status_code == 200, response.text
    return response.json()


GOOD_ANSWER = (
    "我会把题目、参考答案、评分 rubric、技能标签和来源结构化入库，"
    "用 pgvector 做 Top-K 检索，再按 JD 和简历过滤，评分时引用用户回答证据。"
)
WEAK_ANSWER = "我不太清楚这个知识点。"


def test_interview_graph_route_next_step_unit_rules() -> None:
    assert route_next_step({"user_action": "finish"})["next_step"] == "finish"
    assert route_next_step({"error": "boom"})["next_step"] == "finish"

    weak_state = {"last_score": 55, "has_followup": True, "followup_depth": 0}
    assert route_next_step(weak_state)["next_step"] == "follow_up"

    no_more_followup = {
        "last_score": 55,
        "has_followup": True,
        "followup_depth": MAX_FOLLOWUP_DEPTH,
        "interview_plan": {"must_cover_skills": []},
        "main_question_count": 1,
        "max_questions": 3,
        "question_count": 1,
    }
    assert route_next_step(no_more_followup)["next_step"] == "next_question"

    reached_max = {
        "main_question_count": 3,
        "max_questions": 3,
        "question_count": 3,
        "interview_plan": {"must_cover_skills": []},
    }
    assert route_next_step(reached_max)["next_step"] == "wrap_up"

    loop_protection = {
        "main_question_count": 2,
        "max_questions": 2,
        "question_count": 7,
        "interview_plan": {"must_cover_skills": []},
    }
    assert route_next_step(loop_protection)["next_step"] == "finish"

    normal_next = {
        "main_question_count": 1,
        "max_questions": 3,
        "question_count": 1,
        "interview_plan": {"must_cover_skills": []},
    }
    assert route_next_step(normal_next)["next_step"] == "next_question"


def test_interview_graph_weak_answer_followup_then_finish(client: TestClient) -> None:
    token = _register_and_login(client, "v04-graph-followup@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_pool_job(client, token)

    first = _start_interview(client, headers, job_id, max_questions=1)
    assert first["status"] == "running"
    assert first["checkpoint"]["mode"].startswith("langgraph-")
    assert first["checkpoint"]["resume_session_id"] == first["id"]
    assert first["turns"][0]["question_type"] == "opening"
    assert first["turns"][0]["status"] == "asked"

    intro = _answer(client, headers, first["id"], "我主要负责后端和检索模块。")
    assert intro["status"] == "running"
    assert intro["turns"][0]["status"] == "answered"
    assert intro["turns"][0]["score"] is None
    assert intro["current_turn"]["turn_index"] == 2

    weak = _answer(client, headers, first["id"], WEAK_ANSWER)
    assert weak["status"] == "running"
    assert weak["current_turn"]["is_followup"] is True
    assert weak["current_turn"]["followup_depth"] == 1
    assert weak["turns"][1]["score"] < 60

    second = _answer(client, headers, first["id"], "还是没有说到点上。")
    assert second["status"] == "running"
    assert second["current_turn"]["question_type"] == "closing"

    third = _answer(client, headers, first["id"], "我想问一下团队更看重哪类候选人。")
    assert third["status"] == "completed"
    assert third["main_questions_answered"] == 1
    assert third["report"]["total_score"] is not None
    assert third["report"]["question_count"] == 2


def test_interview_graph_checkpoint_resume_and_active_finish(client: TestClient) -> None:
    token = _register_and_login(client, "v04-graph-resume@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_pool_job(client, token)

    session = _start_interview(client, headers, job_id, max_questions=3)
    intro = _answer(client, headers, session["id"], "我做过后端、检索和数据处理。")
    assert intro["status"] == "running"
    assert intro["turns"][0]["score"] is None

    after_first = _answer(client, headers, session["id"], GOOD_ANSWER)
    assert after_first["status"] == "running"
    assert after_first["turns"][1]["score"] >= 70
    assert after_first["current_turn"]["is_followup"] is False
    assert after_first["current_turn"]["turn_index"] == 3

    finish = client.post(f"/api/v1/interviews/{session['id']}/finish", headers=headers)
    assert finish.status_code == 200, finish.text
    completed = finish.json()
    assert completed["status"] == "completed"
    assert completed["main_questions_answered"] == 1
    assert completed["report"]["total_score"] > 0
    assert completed["report"]["question_count"] == 1
    assert completed["checkpoint"]["mode"].startswith("langgraph-")


def test_interview_report_has_v04_dimensions_and_previous_reports(client: TestClient) -> None:
    token = _register_and_login(client, "v04-report-compare@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_pool_job(client, token)

    first = _start_interview(client, headers, job_id, max_questions=1)
    _answer(client, headers, first["id"], "我主要负责后端和检索。")
    first_completed = _answer(client, headers, first["id"], GOOD_ANSWER)
    assert first_completed["status"] == "running"
    first_finished = _answer(client, headers, first["id"], "我想问团队更重视什么。")
    assert first_finished["status"] == "completed"

    second = _start_interview(client, headers, job_id, max_questions=1)
    _answer(client, headers, second["id"], "我主要负责后端和检索。")
    second_completed = _answer(client, headers, second["id"], GOOD_ANSWER)
    assert second_completed["status"] == "running"
    second_finished = _answer(client, headers, second["id"], "我想问团队更重视什么。")
    assert second_finished["status"] == "completed"

    report = second_finished["report"]
    assert report["report_version"] == "langgraph-report-v1"
    assert report["skill_dimensions"]
    assert all(
        {"skill", "score", "question_count"} <= set(dimension.keys())
        for dimension in report["skill_dimensions"]
    )
    assert isinstance(report["fact_based_analysis"], list)
    assert isinstance(report["inference_notes"], list)
    assert len(report["previous_reports"]) == 1
    previous = report["previous_reports"][0]
    assert previous["session_id"] == first_finished["id"]
    assert previous["total_score"] is not None
    assert previous["question_count"] == 1


def test_interview_retrieval_differs_between_agent_and_rag_jobs(client: TestClient) -> None:
    token = _register_and_login(client, "v04-retrieval-diff@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)

    agent_resume_id = _upload_resume(
        client,
        token,
        "Python FastAPI LangGraph Agent 项目，实现工具调用、状态机与多智能体协作。",
    )
    rag_resume_id = _upload_resume(
        client,
        token,
        "Python 向量检索项目，使用 Embedding 与 pgvector 做召回、重排和分块。",
    )

    agent_job_id = _create_pool_job(
        client,
        token,
        title="AI Agent 开发实习生",
        description="负责 Python、FastAPI、LangGraph 和 AI Agent 工具开发。",
        tags=["Python", "FastAPI", "Agent", "LangGraph"],
    )
    rag_job_id = _create_keyword_pool_job(
        client,
        token,
        keyword="RAG",
        title="RAG 算法实习生",
        company="向量科技",
        description="负责 Embedding、向量数据库、检索召回与 Rerank 优化。",
        tags=["RAG", "Embedding", "pgvector", "Python"],
    )

    agent_session = _start_interview(
        client,
        headers,
        agent_job_id,
        max_questions=2,
        resume_version_id=agent_resume_id,
    )
    rag_session = _start_interview(
        client,
        headers,
        rag_job_id,
        max_questions=2,
        resume_version_id=rag_resume_id,
    )

    agent_intro = _answer(client, headers, agent_session["id"], "我做过 Agent 和工具调用相关项目。")
    rag_intro = _answer(client, headers, rag_session["id"], "我做过向量检索和 RAG 相关项目。")

    agent_first = agent_intro["current_turn"]
    rag_first = rag_intro["current_turn"]
    assert agent_first["question_bank_item_external_id"]
    assert rag_first["question_bank_item_external_id"]
    agent_tags = set(agent_intro["turns"][1]["skill_tags"])
    rag_tags = set(rag_intro["turns"][1]["skill_tags"])
    assert agent_first["question_bank_item_external_id"] != rag_first[
        "question_bank_item_external_id"
    ] or agent_tags != rag_tags
