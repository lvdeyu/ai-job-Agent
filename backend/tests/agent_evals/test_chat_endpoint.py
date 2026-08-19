from __future__ import annotations

import json

from fastapi.testclient import TestClient

from tests.agent_evals.fake_llm import FakeLLMClient
from tests.test_v01_account_config_resume import _register_and_login
from tests.test_v01_account_config_resume import client as client
from tests.test_v01_job_evaluation import _create_job_for_user, _setup_profile_and_resume


def _start_interview(
    client: TestClient,
    headers: dict[str, str],
    job_id: str,
    *,
    max_questions: int = 3,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/interviews",
        headers=headers,
        json={"job_id": job_id, "max_questions": max_questions},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _add_job_to_pool(
    client: TestClient,
    headers: dict[str, str],
    job_id: str,
) -> None:
    response = client.post(f"/api/v1/jobs/{job_id}/pool", headers=headers)
    assert response.status_code == 200, response.text


def _sse_events(response: object) -> list[dict[str, object]]:
    text = str(response.text)  # type: ignore[attr-defined]
    events: list[dict[str, object]] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            events.append(json.loads(line[len("data:") :].strip()))
    return events


def test_chat_fallback_answers_and_advances(client: TestClient) -> None:
    token = _register_and_login(client, "chat-fallback@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(client, token)
    _add_job_to_pool(client, headers, job_id)
    session = _start_interview(client, headers, job_id)

    response = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert response.status_code == 200, response.text
    events = _sse_events(response)
    event_types = [str(event["type"]) for event in events]
    assert "assistant_message" in event_types
    assert "session_state" in event_types
    assert "done" in event_types

    state = next(event["session"] for event in events if event["type"] == "session_state")
    assert state["turns"][0]["question_type"] == "opening"
    assert state["turns"][0]["status"] == "answered"
    assert state["turns"][0]["score"] is None
    assert state["current_turn"]["turn_index"] == 2

    second = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我会把题目、参考答案、评分 rubric、技能标签和来源结构化入库，用 pgvector 做 Top-K 检索。"},
    )
    assert second.status_code == 200, second.text
    second_events = _sse_events(second)
    second_state = next(event["session"] for event in second_events if event["type"] == "session_state")
    assert second_state["turns"][1]["status"] == "answered"
    assert second_state["turns"][1]["score"] is not None

    messages = client.get(f"/api/v1/interviews/{session['id']}/messages", headers=headers)
    assert messages.status_code == 200, messages.text
    assert len(messages.json()) >= 3
    roles = {str(message["role"]) for message in messages.json()}
    assert {"user", "assistant"} <= roles


def test_chat_llm_flow_creates_next_turn(client: TestClient, monkeypatch: object) -> None:
    from app.api.routes import interviews as interviews_route

    fake = FakeLLMClient(
        decisions=[
            {
                "action": "next",
                "message": "好的，我们进入下一题，请介绍你的项目经历。",
                "question_text": "请结合项目经历说明你负责的模块和解决的问题。",
                "reason": "golden test",
            }
        ]
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        interviews_route,
        "get_llm_client",
        lambda db, user_id: fake,
    )

    token = _register_and_login(client, "chat-llm@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(client, token)
    _add_job_to_pool(client, headers, job_id)
    session = _start_interview(client, headers, job_id)

    response = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert response.status_code == 200, response.text
    events = _sse_events(response)
    event_types = [str(event["type"]) for event in events]
    assert "assistant_message" in event_types
    assert "score" not in event_types

    state = next(event["session"] for event in events if event["type"] == "session_state")
    assert state["turns"][0]["question_type"] == "opening"
    assert state["turns"][0]["status"] == "answered"
    assert state["turns"][1]["status"] == "asked"
    assert state["turns"][1]["turn_index"] == 2


def test_chat_llm_questions_appear_in_stream_and_messages(
    client: TestClient,
    monkeypatch: object,
) -> None:
    from app.api.routes import interviews as interviews_route

    next_question = "请结合项目经历说明你如何设计检索、评分和证据链。"
    followup_question = "请再补充一个具体的技术边界或失败案例。"
    fake = FakeLLMClient(
        decisions=[
            {
                "action": "next",
                "message": "好的，我们继续下一题。",
                "question_text": next_question,
                "reason": "golden question visible",
            },
            {
                "action": "followup",
                "message": "我再追问一下。",
                "question_text": followup_question,
                "reason": "golden followup visible",
            },
        ]
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        interviews_route,
        "get_llm_client",
        lambda db, user_id: fake,
    )

    token = _register_and_login(client, "chat-question-visible@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(client, token)
    _add_job_to_pool(client, headers, job_id)
    session = _start_interview(client, headers, job_id)

    intro = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert intro.status_code == 200, intro.text

    first = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我负责检索模块，使用 pgvector 和 LangGraph 完成。"},
    )
    assert first.status_code == 200, first.text
    first_events = _sse_events(first)
    assert any(
        next_question in str(event.get("message") or "")
        for event in first_events
        if event["type"] == "assistant_message"
    )

    second = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "核心模块是证据链和评分，答案已包含边界说明。"},
    )
    assert second.status_code == 200, second.text
    second_events = _sse_events(second)
    assert any(
        followup_question in str(event.get("message") or "")
        for event in second_events
        if event["type"] == "assistant_message"
    )

    messages = client.get(f"/api/v1/interviews/{session['id']}/messages", headers=headers)
    assert messages.status_code == 200, messages.text
    assistant_contents = [
        str(message["content"]) for message in messages.json() if message["role"] == "assistant"
    ]
    assert any(next_question in content for content in assistant_contents)
    assert any(followup_question in content for content in assistant_contents)


def test_chat_llm_close_generates_report_and_memory(
    client: TestClient,
    monkeypatch: object,
) -> None:
    from app.api.routes import interviews as interviews_route

    fake = FakeLLMClient(
        decisions=[
            {
                "action": "close",
                "message": "面试到此结束，感谢你的参与。",
                "reason": "golden close",
            }
        ]
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        interviews_route,
        "get_llm_client",
        lambda db, user_id: fake,
    )

    token = _register_and_login(client, "chat-llm-close@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(client, token)
    _add_job_to_pool(client, headers, job_id)
    session = _start_interview(client, headers, job_id, max_questions=1)

    intro = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert intro.status_code == 200, intro.text

    response = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "完整回答，包含检索、评分、证据、pgvector 和 checkpoint。"},
    )
    assert response.status_code == 200, response.text
    events = _sse_events(response)
    state = next(event["session"] for event in events if event["type"] == "session_state")
    assert state["status"] == "running"
    assert state["current_turn"]["question_type"] == "closing"

    closing = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我想了解团队对项目质量和成长空间的要求。"},
    )
    assert closing.status_code == 200, closing.text
    closing_events = _sse_events(closing)
    closing_state = next(
        event["session"] for event in closing_events if event["type"] == "session_state"
    )
    assert closing_state["status"] == "completed"
    assert closing_state["report"] is not None
    assert closing_state["report"]["total_score"] > 0

    detail = client.get(f"/api/v1/interviews/{session['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"

    events = client.get(f"/api/v1/interviews/{session['id']}/events", headers=headers)
    assert events.status_code == 200, events.text
    event_types = {str(item["event_type"]) for item in events.json()}
    assert "llm_decision" in event_types


def test_chat_llm_guardrail_caps_questions(
    client: TestClient,
    monkeypatch: object,
) -> None:
    from app.api.routes import interviews as interviews_route

    fake = FakeLLMClient(
        decisions=[
            {
                "action": "next",
                "message": "我们继续下一题。",
                "reason": "golden guardrail",
            }
        ]
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        interviews_route,
        "get_llm_client",
        lambda db, user_id: fake,
    )

    token = _register_and_login(client, "chat-llm-guardrail@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(client, token)
    _add_job_to_pool(client, headers, job_id)
    session = _start_interview(client, headers, job_id, max_questions=1)

    intro = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert intro.status_code == 200, intro.text

    response = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "完整回答，包含检索、评分、证据和 checkpoint。"},
    )
    assert response.status_code == 200, response.text
    events = _sse_events(response)
    state = next(event["session"] for event in events if event["type"] == "session_state")
    assert state["status"] == "running"
    assert state["main_questions_answered"] == 1
    assert state["current_turn"]["question_type"] == "closing"
    assert state["report"] is None


def test_chat_llm_failure_falls_back_to_rules(
    client: TestClient,
    monkeypatch: object,
) -> None:
    from app.api.routes import interviews as interviews_route

    fake = FakeLLMClient(fail_tools=True, fail_json=True)
    monkeypatch.setattr(  # type: ignore[attr-defined]
        interviews_route,
        "get_llm_client",
        lambda db, user_id: fake,
    )

    token = _register_and_login(client, "chat-llm-fail@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(client, token)
    _add_job_to_pool(client, headers, job_id)
    session = _start_interview(client, headers, job_id)

    intro = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert intro.status_code == 200, intro.text

    response = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "完整回答，包含检索、评分、证据、pgvector 和 checkpoint。"},
    )
    assert response.status_code == 200, response.text
    events = _sse_events(response)
    event_types = [str(event["type"]) for event in events]
    assert "llm_error" in event_types
    assert "error" not in event_types
    state = next(event["session"] for event in events if event["type"] == "session_state")
    assert state["status"] == "running"
    assert len(state["turns"]) >= 2
    assert state["turns"][-1]["status"] == "asked"


def test_chat_llm_tools_then_decision(
    client: TestClient,
    monkeypatch: object,
) -> None:
    from app.api.routes import interviews as interviews_route
    from app.services.llm import ToolCall

    fake = FakeLLMClient(
        tool_calls=[ToolCall(name="get_job_context", arguments={})],
        decisions=[
            {
                "action": "next",
                "message": "结合岗位背景，我们进入下一题。",
                "question_text": "请说明你如何设计模拟面试 Agent 的工具调用。",
                "reason": "golden tools then decision",
            }
        ],
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        interviews_route,
        "get_llm_client",
        lambda db, user_id: fake,
    )

    token = _register_and_login(client, "chat-llm-tools@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(client, token)
    _add_job_to_pool(client, headers, job_id)
    session = _start_interview(client, headers, job_id)

    intro = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert intro.status_code == 200, intro.text

    response = client.post(
        f"/api/v1/interviews/{session['id']}/chat",
        headers=headers,
        json={"content": "完整回答，包含检索、评分、证据和 checkpoint。"},
    )
    assert response.status_code == 200, response.text
    events = _sse_events(response)
    event_types = [str(event["type"]) for event in events]
    assert "tool_used" not in event_types
    assert "assistant_message" in event_types
    state = next(event["session"] for event in events if event["type"] == "session_state")
    assert state["status"] == "running"
    assert len(state["turns"]) >= 2
    assert state["turns"][-1]["status"] == "asked"

    recorded = client.get(f"/api/v1/interviews/{session['id']}/events", headers=headers)
    assert recorded.status_code == 200, recorded.text
    recorded_types = {str(item["event_type"]) for item in recorded.json()}
    assert "tool_call" in recorded_types


def test_llm_mode_recalls_long_term_memory(
    client: TestClient,
    monkeypatch: object,
) -> None:
    from app.api.routes import interviews as interviews_route

    token = _register_and_login(client, "chat-llm-memory@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    _setup_profile_and_resume(client, token)
    job_id = _create_job_for_user(client, token)
    _add_job_to_pool(client, headers, job_id)

    first = FakeLLMClient(
        decisions=[
            {
                "action": "close",
                "message": "面试结束，感谢参与。",
                "reason": "close for memory",
            }
        ]
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        interviews_route,
        "get_llm_client",
        lambda db, user_id: first,
    )
    session_one = _start_interview(client, headers, job_id, max_questions=1)
    intro_one = client.post(
        f"/api/v1/interviews/{session_one['id']}/chat",
        headers=headers,
        json={"content": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert intro_one.status_code == 200, intro_one.text
    response = client.post(
        f"/api/v1/interviews/{session_one['id']}/chat",
        headers=headers,
        json={"content": "完整回答，包含检索、评分、证据和 checkpoint。"},
    )
    assert response.status_code == 200, response.text
    closing_response = client.post(
        f"/api/v1/interviews/{session_one['id']}/chat",
        headers=headers,
        json={"content": "我想了解团队对项目质量和成长空间的要求。"},
    )
    assert closing_response.status_code == 200, closing_response.text
    state_one = next(
        event["session"] for event in _sse_events(closing_response) if event["type"] == "session_state"
    )
    assert state_one["status"] == "completed"

    second = FakeLLMClient(
        decisions=[
            {
                "action": "next",
                "message": "我们继续下一题。",
                "question_text": "请说明如何设计工具调用。",
                "reason": "next after memory",
            }
        ]
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        interviews_route,
        "get_llm_client",
        lambda db, user_id: second,
    )
    session_two = _start_interview(client, headers, job_id, max_questions=3)
    intro_two = client.post(
        f"/api/v1/interviews/{session_two['id']}/chat",
        headers=headers,
        json={"content": "我主要做后端和检索模块，负责过 FastAPI、pgvector 和 LangGraph。"},
    )
    assert intro_two.status_code == 200, intro_two.text
    response = client.post(
        f"/api/v1/interviews/{session_two['id']}/chat",
        headers=headers,
        json={"content": "完整回答，包含检索、评分、证据和 checkpoint。"},
    )
    assert response.status_code == 200, response.text
    closing_two = client.post(
        f"/api/v1/interviews/{session_two['id']}/chat",
        headers=headers,
        json={"content": "我还想了解团队怎么衡量项目完成质量。"},
    )
    assert closing_two.status_code == 200, closing_two.text
    assert any("长期记忆" in prompt for prompt in second.system_prompts)
