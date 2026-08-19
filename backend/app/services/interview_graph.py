"""LangGraph interview state machine (V0.4 step 2)."""
from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from psycopg_pool import ConnectionPool
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import InterviewSession, InterviewTurn, QuestionBankItem
from app.services.interview import (
    CLOSING_QUESTION_TYPE,
    OPENING_QUESTION_TYPE,
    SCORING_MODE,
    _contains_casefold,
    _load,
    _move_job_application_status,
    active_retrieval_mode,
    build_interview_report,
    evaluate_interview_answer,
    retrieve_interview_questions,
)

MIN_MAIN_QUESTIONS_BEFORE_EARLY_FINISH = 5
MAX_FOLLOWUP_DEPTH = 2

_graph_by_dialect: dict[str, Any] = {}
_saver_by_dialect: dict[str, Any] = {}
_db_context: ContextVar[Session | None] = ContextVar("interview_graph_db", default=None)


class InterviewState(TypedDict, total=False):
    session_id: str
    user_id: str
    job_id: str
    resume_version_id: str
    job_snapshot: dict[str, Any]
    resume_snapshot: dict[str, Any]
    retrieval_queries: list[str]
    retrieved_question_bank_items: list[dict[str, Any]]
    active_rubric: dict[str, Any]
    interview_plan: dict[str, Any]
    current_question: dict[str, Any] | None
    question_history: list[dict[str, Any]]
    answer_history: list[dict[str, Any]]
    covered_skills: list[str]
    uncovered_skills: list[str]
    difficulty: str
    followup_depth: int
    last_turn_id: str
    question_count: int
    main_question_count: int
    max_questions: int
    decision_summary: str
    report: dict[str, Any] | None
    status: str
    user_action: str
    next_step: str
    user_answer: str
    last_score: float
    has_followup: bool
    error: str | None
    retrieval_mode: str
    scoring_mode: str
    retrieval_filters: list[dict[str, Any]]
    closing_completed: bool


SKILL_VOCABULARY = [
    "Python",
    "FastAPI",
    "RAG",
    "Agent",
    "LangGraph",
    "LangChain",
    "LLM",
    "SQL",
    "Redis",
    "Docker",
    "pgvector",
    "MCP",
    "Embedding",
    "ReAct",
    "Function Calling",
    "Multi-Agent",
    "LoRA",
    "CoT",
    "Rerank",
    "Vector Database",
    "Checkpoint",
    "Workflow",
    "SSE",
    "WebSocket",
    "Transformer",
    "Memory",
    "Chain",
    "Reflection",
    "Attention",
    "RLHF",
    "DPO",
    "Llm Engineering",
    "Llm Tool Use",
    "Backend",
    "Deep Research",
    "Chunking",
    "Query Rewrite",
    "State Machine",
    "Project Deep Dive",
]

QUESTION_TYPE_ORDER = ["skill", "project_deep_dive", "scenario", "foundation"]


# --------------------------------------------------------------------------
# Graph nodes
# --------------------------------------------------------------------------
def _db() -> Session:
    session = _db_context.get()
    if session is None:
        raise RuntimeError("interview graph db context is not set")
    return session


def load_interview_context(state: InterviewState) -> dict[str, Any]:
    db = _db()
    interview = db.get(InterviewSession, state["session_id"])
    if interview is None:
        raise RuntimeError(f"interview session {state['session_id']} not found")
    job = interview.job
    resume_version = interview.resume_version
    return {
        "job_snapshot": _job_snapshot(job),
        "resume_snapshot": _resume_snapshot(resume_version),
        "retrieval_mode": active_retrieval_mode(db),
        "scoring_mode": SCORING_MODE,
    }


def analyze_interview_targets(state: InterviewState) -> dict[str, Any]:
    job = state.get("job_snapshot", {})
    resume = state.get("resume_snapshot", {})
    context = _target_context(job, resume)
    job_context = " ".join(
        [
            job.get("title") or "",
            job.get("tags") or "",
            job.get("description") or "",
        ]
    ).lower()
    must_cover = [skill for skill in SKILL_VOCABULARY if _contains_casefold(job_context, skill)]
    if not must_cover:
        must_cover = [skill for skill in SKILL_VOCABULARY if _contains_casefold(context, skill)]
    risk_points = _project_risk_points(resume)
    gaps = _experience_gaps(job, resume)
    return {
        "uncovered_skills": must_cover,
        "interview_plan": {
            "must_cover_skills": must_cover,
            "project_risk_points": risk_points,
            "experience_gaps": gaps,
            "difficulty": "medium",
            "question_type_targets": {
                "skill": 3,
                "project_deep_dive": 2,
                "scenario": 1,
                "foundation": 1,
            },
            "max_main_questions": state.get("max_questions", 8),
        },
        "difficulty": "medium",
    }


def retrieve_interview_knowledge(state: InterviewState) -> dict[str, Any]:
    db = _db()
    interview = db.get(InterviewSession, state["session_id"])
    job = interview.job
    resume_version = interview.resume_version
    evaluation = interview.job_evaluation
    queries = _build_retrieval_queries(state)
    items = retrieve_interview_questions(
        db=db,
        job=job,
        resume_version=resume_version,
        evaluation=evaluation,
        limit=16,
    )
    serialized = [
        _serialize_question(item, rank=rank)
        for rank, item in enumerate(items)
    ]
    return {"retrieval_queries": queries, "retrieved_question_bank_items": serialized}


def build_interview_plan(state: InterviewState) -> dict[str, Any]:
    plan = dict(state.get("interview_plan") or {})
    plan["question_type_targets"] = _type_targets_for_plan(state)
    plan["difficulty"] = state.get("difficulty") or "medium"
    return {"interview_plan": plan}


def select_question(state: InterviewState) -> dict[str, Any]:
    if state.get("question_count", 0) == 0:
        title = state.get("job_snapshot", {}).get("title") or "这个岗位"
        return {
            "current_question": {
                "id": None,
                "question_text": f"欢迎来到本场模拟面试。先请你做一个 1 分钟左右的自我介绍，重点说说你和 {title} 的匹配点。",
                "question_type": OPENING_QUESTION_TYPE,
                "difficulty": "easy",
                "skill_tags": [],
                "reference_answer": "",
                "scoring_rubric": [],
                "followup_suggestions": [],
                "is_followup": False,
                "followup_depth": 0,
                "source": {"kind": "opening"},
                "retrieval_rank": -1,
            },
            "decision_summary": "模拟面试开场并引导自我介绍",
        }
    asked_ids = {
        question.get("id")
        for question in state.get("question_history", [])
        if question.get("id")
    }
    plan = state.get("interview_plan") or {}
    covered = set(state.get("covered_skills") or [])
    uncovered = [skill for skill in (plan.get("must_cover_skills") or []) if skill not in covered]
    candidates = [
        question
        for question in state.get("retrieved_question_bank_items", [])
        if question.get("id") not in asked_ids
    ]
    chosen = _pick_best_question(candidates, uncovered)
    if chosen is not None:
        return {"current_question": chosen, "decision_summary": "从 RAG 检索结果中选择高相关题目"}
    generated = _generate_question(state)
    return {
        "current_question": generated,
        "decision_summary": "题库检索不足，基于 JD/简历生成专属问题",
    }


def ask_question(state: InterviewState) -> dict[str, Any]:
    db = _db()
    question = state.get("current_question")
    if question is None:
        raise RuntimeError("no current question to ask")
    turn_index = state.get("question_count", 0) + 1
    turn = InterviewTurn(
        session_id=state["session_id"],
        user_id=state["user_id"],
        question_bank_item_id=question.get("id"),
        turn_index=turn_index,
        question_text=question["question_text"],
        question_type=question.get("question_type") or "skill",
        skill_tags_json=json.dumps(question.get("skill_tags") or [], ensure_ascii=False),
        reference_answer_snapshot=question.get("reference_answer") or "",
        scoring_rubric_json=json.dumps(question.get("scoring_rubric") or [], ensure_ascii=False),
        followup_suggestions_json=json.dumps(
            question.get("followup_suggestions") or [], ensure_ascii=False
        ),
        is_followup=bool(question.get("is_followup")),
        followup_depth=question.get("followup_depth") or 0,
        parent_turn_id=question.get("parent_turn_id"),
        status="asked",
    )
    db.add(turn)
    db.flush()
    history = list(state.get("question_history") or [])
    history.append(
        {
            "id": question.get("id"),
            "turn_id": turn.id,
            "question_text": question["question_text"],
        }
    )
    return {
        "current_question": question,
        "question_history": history,
        "question_count": turn_index,
        "last_turn_id": turn.id,
        "status": "running",
    }


def wait_for_user_answer(state: InterviewState) -> dict[str, Any]:
    resume_value = interrupt({"question": state.get("current_question")})
    if isinstance(resume_value, dict) and resume_value.get("action") == "finish":
        return {"user_action": "finish", "user_answer": ""}
    answer = (
        resume_value.get("answer")
        if isinstance(resume_value, dict)
        else str(resume_value or "")
    )
    return {"user_action": "answer", "user_answer": answer}


def evaluate_answer(state: InterviewState) -> dict[str, Any]:
    if state.get("user_action") == "finish":
        return {"last_score": 0.0, "decision_summary": "用户主动结束面试"}
    db = _db()
    last_turn_id = state.get("last_turn_id")
    if not last_turn_id:
        raise RuntimeError("interview turn id missing before evaluation")
    turn = db.get(InterviewTurn, last_turn_id)
    if turn is None:
        raise RuntimeError(f"interview turn {last_turn_id} not found")
    if turn.question_type == OPENING_QUESTION_TYPE:
        turn.answer_text = state.get("user_answer") or ""
        turn.score = None
        turn.feedback = "已记录自我介绍"
        turn.evidence_json = json.dumps([], ensure_ascii=False)
        turn.status = "answered"
        turn.answered_at = datetime.now(UTC)
        db.flush()
        return {
            "has_followup": False,
            "followup_depth": 0,
            "last_score": 0.0,
            "main_question_count": state.get("main_question_count", 0),
            "status": "running",
        }
    if turn.question_type == CLOSING_QUESTION_TYPE:
        turn.answer_text = state.get("user_answer") or ""
        turn.score = None
        turn.feedback = "已记录用户反问"
        turn.evidence_json = json.dumps([], ensure_ascii=False)
        turn.status = "answered"
        turn.answered_at = datetime.now(UTC)
        db.flush()
        return {
            "closing_completed": True,
            "has_followup": False,
            "followup_depth": 0,
            "last_score": 0.0,
            "main_question_count": state.get("main_question_count", 0),
            "status": "running",
        }
    result = evaluate_interview_answer(turn, state.get("user_answer") or "")
    turn.answer_text = state.get("user_answer") or ""
    turn.score = result["score"]
    turn.feedback = result["feedback"]
    turn.evidence_json = json.dumps(result.get("evidence") or [], ensure_ascii=False)
    turn.status = "answered"
    turn.answered_at = datetime.now(UTC)
    db.flush()
    covered = list(state.get("covered_skills") or [])
    for skill in _load(turn.skill_tags_json, []):
        if skill and skill not in covered:
            covered.append(skill)
    has_followup = bool(_load(turn.followup_suggestions_json, []))
    main_question_count = state.get("main_question_count", 0)
    if not turn.is_followup:
        main_question_count += 1
    return {
        "covered_skills": covered,
        "last_score": float(result["score"]),
        "has_followup": has_followup,
        "followup_depth": turn.followup_depth,
        "main_question_count": main_question_count,
        "status": "running",
    }


def route_next_step(state: InterviewState) -> dict[str, Any]:
    if state.get("user_action") == "finish":
        decision = "finish"
    elif state.get("closing_completed"):
        decision = "finish"
    elif state.get("error"):
        decision = "finish"
    elif state.get("question_count", 0) > state.get("max_questions", 8) * 3:
        decision = "finish"
    elif (
        state.get("last_score", 0) < 70
        and state.get("has_followup")
        and state.get("followup_depth", 0) < MAX_FOLLOWUP_DEPTH
    ):
        decision = "follow_up"
    else:
        plan = state.get("interview_plan") or {}
        must_cover = plan.get("must_cover_skills") or []
        covered = set(state.get("covered_skills") or [])
        main_count = state.get("main_question_count", 0)
        max_questions = state.get("max_questions", 8)
        if main_count >= max_questions:
            decision = "wrap_up"
        elif (
            main_count >= MIN_MAIN_QUESTIONS_BEFORE_EARLY_FINISH
            and must_cover
            and all(skill in covered for skill in must_cover)
        ):
            decision = "wrap_up"
        else:
            decision = "next_question"
    return {"next_step": decision}


def _route_after_evaluate(state: InterviewState) -> str:
    return state.get("next_step") or "next_question"


def ask_closing(state: InterviewState) -> dict[str, Any]:
    db = _db()
    interview = db.get(InterviewSession, state["session_id"])
    if interview is None:
        raise RuntimeError(f"interview session {state['session_id']} not found")
    next_index = max((turn.turn_index for turn in interview.turns), default=0) + 1
    question = {
        "id": None,
        "question_text": "今天的面试先到这里，最后想请你反问我一个问题，你最想了解什么？",
        "question_type": CLOSING_QUESTION_TYPE,
        "difficulty": "easy",
        "skill_tags": [],
        "reference_answer": "",
        "scoring_rubric": [],
        "followup_suggestions": [],
        "is_followup": False,
        "followup_depth": 0,
        "source": {"kind": "closing"},
        "retrieval_rank": -1,
    }
    turn = InterviewTurn(
        session_id=state["session_id"],
        user_id=state["user_id"],
        question_bank_item_id=None,
        turn_index=next_index,
        question_text=question["question_text"],
        question_type=question["question_type"],
        skill_tags_json=json.dumps([], ensure_ascii=False),
        reference_answer_snapshot="",
        scoring_rubric_json="[]",
        followup_suggestions_json="[]",
        is_followup=False,
        followup_depth=0,
        status="asked",
    )
    db.add(turn)
    db.flush()
    history = list(state.get("question_history") or [])
    history.append(
        {
            "id": None,
            "turn_id": turn.id,
            "question_text": question["question_text"],
        }
    )
    return {
        "current_question": question,
        "question_history": history,
        "question_count": next_index,
        "last_turn_id": turn.id,
        "status": "running",
    }


def ask_followup(state: InterviewState) -> dict[str, Any]:
    db = _db()
    parent = db.get(InterviewTurn, state.get("last_turn_id"))
    if parent is None:
        raise RuntimeError(f"interview turn {state.get('last_turn_id')} not found")
    followups = _load(parent.followup_suggestions_json, [])
    depth = parent.followup_depth + 1
    suggestion_index = min(parent.followup_depth, len(followups) - 1)
    question_text = followups[suggestion_index]
    question = {
        "id": None,
        "question_text": question_text,
        "question_type": "followup",
        "difficulty": "medium",
        "skill_tags": _load(parent.skill_tags_json, []),
        "reference_answer": parent.reference_answer_snapshot,
        "scoring_rubric": _load(parent.scoring_rubric_json, []),
        "followup_suggestions": [],
        "is_followup": True,
        "followup_depth": depth,
        "parent_turn_id": parent.id,
        "source": {"kind": "followup", "parent_question_id": parent.question_bank_item_id},
        "retrieval_rank": -1,
    }
    db.flush()
    turn_index = state.get("question_count", 0) + 1
    turn = InterviewTurn(
        session_id=state["session_id"],
        user_id=state["user_id"],
        question_bank_item_id=None,
        parent_turn_id=parent.id,
        turn_index=turn_index,
        question_text=question_text,
        question_type="followup",
        skill_tags_json=parent.skill_tags_json,
        reference_answer_snapshot=parent.reference_answer_snapshot,
        scoring_rubric_json=parent.scoring_rubric_json,
        followup_suggestions_json="[]",
        is_followup=True,
        followup_depth=depth,
        status="asked",
    )
    db.add(turn)
    db.flush()
    history = list(state.get("question_history") or [])
    history.append({"id": None, "turn_id": turn.id, "question_text": question_text})
    return {
        "current_question": question,
        "question_history": history,
        "question_count": turn_index,
        "last_turn_id": turn.id,
        "followup_depth": depth,
        "status": "running",
    }


def generate_interview_report(state: InterviewState) -> dict[str, Any]:
    db = _db()
    interview = db.get(InterviewSession, state["session_id"])
    interview.main_questions_answered = state.get("main_question_count", 0)
    db.flush()
    report = build_interview_report(interview, db=db)
    return {"report": report, "status": "completed"}


def persist_report(state: InterviewState) -> dict[str, Any]:
    db = _db()
    interview = db.get(InterviewSession, state["session_id"])
    report = state.get("report")
    if report is not None:
        interview.report_json = json.dumps(report, ensure_ascii=False)
    interview.status = "completed"
    interview.completed_at = datetime.now(UTC)
    interview.main_questions_answered = state.get("main_question_count", 0)
    _move_job_application_status(interview.job, "REVIEWED", only_from={"INTERVIEWING"})
    db.flush()
    return {"status": "completed"}


# --------------------------------------------------------------------------
# Graph construction
# --------------------------------------------------------------------------
def _build_graph() -> StateGraph:
    graph = StateGraph(InterviewState)
    graph.add_node("load_interview_context", load_interview_context)
    graph.add_node("analyze_interview_targets", analyze_interview_targets)
    graph.add_node("retrieve_interview_knowledge", retrieve_interview_knowledge)
    graph.add_node("build_interview_plan", build_interview_plan)
    graph.add_node("select_question", select_question)
    graph.add_node("ask_question", ask_question)
    graph.add_node("wait_for_user_answer", wait_for_user_answer)
    graph.add_node("evaluate_answer", evaluate_answer)
    graph.add_node("route_next_step", route_next_step)
    graph.add_node("ask_followup", ask_followup)
    graph.add_node("ask_closing", ask_closing)
    graph.add_node("generate_interview_report", generate_interview_report)
    graph.add_node("persist_report", persist_report)

    graph.add_edge(START, "load_interview_context")
    graph.add_edge("load_interview_context", "analyze_interview_targets")
    graph.add_edge("analyze_interview_targets", "retrieve_interview_knowledge")
    graph.add_edge("retrieve_interview_knowledge", "build_interview_plan")
    graph.add_edge("build_interview_plan", "select_question")
    graph.add_edge("select_question", "ask_question")
    graph.add_edge("ask_question", "wait_for_user_answer")
    graph.add_edge("wait_for_user_answer", "evaluate_answer")
    graph.add_edge("evaluate_answer", "route_next_step")
    graph.add_conditional_edges(
        "route_next_step",
        _route_after_evaluate,
        {
            "follow_up": "ask_followup",
            "next_question": "select_question",
            "wrap_up": "ask_closing",
            "finish": "generate_interview_report",
        },
    )
    graph.add_edge("ask_followup", "wait_for_user_answer")
    graph.add_edge("ask_closing", "wait_for_user_answer")
    graph.add_edge("generate_interview_report", "persist_report")
    graph.add_edge("persist_report", END)
    return graph


def _get_saver(db: Session) -> Any:
    dialect = db.get_bind().dialect.name
    if dialect in _saver_by_dialect:
        return _saver_by_dialect[dialect]
    if dialect == "postgresql":
        conninfo = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
        pool = ConnectionPool(
            conninfo=conninfo,
            min_size=1,
            max_size=3,
            kwargs={"autocommit": True},
            open=False,
        )
        pool.open()
        saver = PostgresSaver(pool)
        saver.setup()
    else:
        saver = InMemorySaver()
    _saver_by_dialect[dialect] = saver
    return saver


def _get_graph(db: Session) -> Any:
    dialect = db.get_bind().dialect.name
    if dialect not in _graph_by_dialect:
        saver = _get_saver(db)
        _graph_by_dialect[dialect] = _build_graph().compile(checkpointer=saver)
    return _graph_by_dialect[dialect]


def _thread_config(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def run_interview_graph_start(
    *,
    session_id: str,
    db: Session,
    initial_state: InterviewState,
) -> dict[str, Any]:
    graph = _get_graph(db)
    token = _db_context.set(db)
    try:
        return graph.invoke(initial_state, config=_thread_config(session_id))
    finally:
        _db_context.reset(token)


def run_interview_graph_resume(
    *,
    session_id: str,
    db: Session,
    resume_value: Any,
) -> dict[str, Any]:
    graph = _get_graph(db)
    token = _db_context.set(db)
    try:
        return graph.invoke(Command(resume=resume_value), config=_thread_config(session_id))
    finally:
        _db_context.reset(token)


def interview_graph_checkpoint_exists(*, session_id: str, db: Session) -> bool:
    graph = _get_graph(db)
    snapshot = graph.get_state(_thread_config(session_id))
    return bool(snapshot.values)


def interview_graph_checkpoint_mode(db: Session) -> str:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        return "langgraph-postgres-checkpoint-v1"
    return "langgraph-memory-checkpoint-v1"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _job_snapshot(job: Any) -> dict[str, Any]:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "salary": job.salary,
        "experience": job.experience,
        "education": job.education,
        "tags": job.tags,
        "description": job.description,
    }


def _resume_snapshot(resume_version: Any) -> dict[str, Any]:
    return {
        "id": resume_version.id,
        "title": getattr(resume_version, "title", None),
        "extracted_text": getattr(resume_version, "extracted_text", ""),
    }


def _target_context(job: dict[str, Any], resume: dict[str, Any]) -> str:
    return " ".join(
        [
            job.get("title") or "",
            job.get("tags") or "",
            job.get("description") or "",
            resume.get("extracted_text") or "",
        ]
    ).lower()


def _project_risk_points(resume: dict[str, Any]) -> list[str]:
    text = resume.get("extracted_text") or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    projects = [line for line in lines if _contains_casefold(line, "项目")]
    return projects[:5]


def _experience_gaps(job: dict[str, Any], resume: dict[str, Any]) -> list[str]:
    job_skills = [
        skill
        for skill in SKILL_VOCABULARY
        if _contains_casefold(job.get("description") or "", skill)
    ]
    resume_text = (resume.get("extracted_text") or "").lower()
    return [skill for skill in job_skills if skill.lower() not in resume_text]


def _build_retrieval_queries(state: InterviewState) -> list[str]:
    job = state.get("job_snapshot", {})
    resume = state.get("resume_snapshot", {})
    plan = state.get("interview_plan") or {}
    queries = [
        " ".join([job.get("title") or "", job.get("description") or ""]),
        resume.get("extracted_text") or "",
    ]
    for skill in (plan.get("must_cover_skills") or [])[:4]:
        queries.append(skill)
    return [query for query in queries if query]


def _serialize_question(item: QuestionBankItem, *, rank: int) -> dict[str, Any]:
    return {
        "id": item.id,
        "external_id": item.external_id,
        "domain": item.domain,
        "question_type": item.question_type,
        "difficulty": item.difficulty,
        "skill_tags": _load(item.skill_tags_json, []),
        "question_text": item.question_text,
        "reference_answer": item.reference_answer,
        "scoring_rubric": _load(item.scoring_rubric_json, []),
        "followup_suggestions": _load(item.followup_suggestions_json, []),
        "source": _load(item.source_json, {}),
        "is_followup": False,
        "followup_depth": 0,
        "retrieval_rank": rank,
    }


def _pick_best_question(
    candidates: list[dict[str, Any]],
    uncovered: list[str],
) -> dict[str, Any] | None:
    if not candidates:
        return None
    uncovered_set = {skill.lower() for skill in uncovered}
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for question in candidates:
        tags = [tag.lower() for tag in question.get("skill_tags") or []]
        coverage = sum(1 for tag in tags if tag in uncovered_set)
        question_type_rank = (
            QUESTION_TYPE_ORDER.index(question.get("question_type"))
            if question.get("question_type") in QUESTION_TYPE_ORDER
            else 99
        )
        scored.append((coverage, question_type_rank, question))
    scored.sort(key=lambda pair: (-pair[0], pair[1], (pair[2].get("retrieval_rank") or 999)))
    return scored[0][2]


def _type_targets_for_plan(state: InterviewState) -> dict[str, int]:
    max_questions = state.get("max_questions", 8)
    targets: dict[str, int] = {}
    for question_type in QUESTION_TYPE_ORDER:
        targets[question_type] = 1
    remaining = max_questions - len(targets)
    index = 0
    while remaining > 0:
        question_type = QUESTION_TYPE_ORDER[index % len(QUESTION_TYPE_ORDER)]
        targets[question_type] = targets.get(question_type, 0) + 1
        remaining -= 1
        index += 1
    return targets


def _generate_question(state: InterviewState) -> dict[str, Any]:
    job = state.get("job_snapshot", {})
    plan = state.get("interview_plan") or {}
    covered = set(state.get("covered_skills") or [])
    uncovered = [skill for skill in (plan.get("must_cover_skills") or []) if skill not in covered]
    skill = uncovered[0] if uncovered else "岗位核心技能"
    question_type = "skill"
    title = job.get("title") or "该岗位"
    question_text = (
        f"结合 JD 对「{skill}」的要求和你的项目经历，"
        f"说明你会如何在 {title} 相关项目中落地，并给出具体实现步骤。"
    )
    reference_answer = (
        f"围绕 {skill} 说明核心概念、适用场景、实现步骤、"
        "边界情况和可观测性，并补充一段项目证据。"
    )
    rubric = [
        {"criterion": "概念理解", "points": 30, "excellent_signal": skill, "weak_signal": ""},
        {
            "criterion": "落地步骤",
            "points": 40,
            "excellent_signal": "实现 步骤 项目",
            "weak_signal": "",
        },
        {
            "criterion": "边界与证据",
            "points": 30,
            "excellent_signal": "边界 证据 可观测",
            "weak_signal": "",
        },
    ]
    return {
        "id": None,
        "external_id": f"generated:{skill}:{len(state.get('question_history') or [])}",
        "domain": "generated",
        "question_type": question_type,
        "difficulty": "medium",
        "skill_tags": [skill],
        "question_text": question_text,
        "reference_answer": reference_answer,
        "scoring_rubric": rubric,
        "followup_suggestions": [f"再追问：{skill} 方案遇到性能瓶颈或边界情况时你会如何优化？"],
        "source": {"kind": "generated_from_jd_resume", "reason": "题库检索结果不足"},
        "is_followup": False,
        "followup_depth": 0,
        "retrieval_rank": -1,
    }
