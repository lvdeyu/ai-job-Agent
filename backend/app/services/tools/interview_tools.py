from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InterviewSession, ResumeProjectItem
from app.services.llm import ToolSpec


@dataclass
class ToolExecutionContext:
    db: Session
    session: InterviewSession


INTERVIEW_TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="search_interview_questions",
        description="根据查询词、题型和技能标签检索面试题库，返回候选题目列表。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询，例如岗位描述或技能关键词"},
                "question_type": {
                    "type": "string",
                    "description": "可选：skill/project_deep_dive/scenario/foundation",
                },
                "skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "技能标签列表",
                },
                "limit": {"type": "integer", "description": "返回数量，默认 6"},
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="get_job_context",
        description="获取当前岗位的 JD、薪资、标签和岗位评测摘要。",
        parameters={"type": "object", "properties": {}},
    ),
    ToolSpec(
        name="get_resume_projects",
        description="获取简历中的项目事实（项目名、职责、技术栈、成果、风险点），只能基于这些事实提问。",
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "可选，指定项目 ID"},
            },
        },
    ),
    ToolSpec(
        name="score_answer",
        description="对用户针对当前题目的回答执行确定性评分，返回分数、反馈和证据。",
        parameters={
            "type": "object",
            "properties": {
                "answer_text": {"type": "string", "description": "用户回答原文"},
            },
            "required": ["answer_text"],
        },
    ),
]


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    context: ToolExecutionContext,
) -> dict[str, Any]:
    handlers: dict[str, Any] = {
        "search_interview_questions": _search_interview_questions,
        "get_job_context": _get_job_context,
        "get_resume_projects": _get_resume_projects,
        "score_answer": _score_answer,
    }
    handler = handlers.get(name)
    if handler is None:
        return {"ok": False, "error": f"未知工具: {name}"}
    try:
        return handler(arguments, context)
    except Exception as exc:  # noqa: BLE001 - tool boundary returns error instead of raising
        return {"ok": False, "error": str(exc)}


def _search_interview_questions(
    arguments: dict[str, Any],
    context: ToolExecutionContext,
) -> dict[str, Any]:
    from app.services.interview import retrieve_interview_questions

    session = context.session
    items = retrieve_interview_questions(
        db=context.db,
        job=session.job,
        resume_version=session.resume_version,
        evaluation=session.job_evaluation,
        limit=int(arguments.get("limit", 6)),
    )
    question_type = arguments.get("question_type")
    skills = [str(skill).lower() for skill in (arguments.get("skills") or [])]
    results: list[dict[str, Any]] = []
    for item in items:
        if question_type and item.question_type != question_type:
            continue
        item_skills = json.loads(item.skill_tags_json or "[]")
        item_skill_set = {str(tag).lower() for tag in item_skills}
        if skills and not any(str(skill).lower() in item_skill_set for skill in skills):
            continue
        results.append(
            {
                "id": item.id,
                "external_id": item.external_id,
                "question_type": item.question_type,
                "difficulty": item.difficulty,
                "skill_tags": item_skills,
                "question_text": item.question_text,
            }
        )
    return {"ok": True, "count": len(results), "items": results}


def _get_job_context(arguments: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
    job = context.session.job
    evaluation = context.session.job_evaluation
    summary = None
    if evaluation is not None:
        summary = {
            "final_score": evaluation.final_score,
            "recommendation": evaluation.recommendation,
            "one_sentence_reason": evaluation.one_sentence_reason,
        }
    return {
        "ok": True,
        "job": {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary": job.salary,
            "experience": job.experience,
            "education": job.education,
            "tags": job.tags,
            "description": (job.description or "")[:1500],
        },
        "evaluation": summary,
    }


def _get_resume_projects(
    arguments: dict[str, Any],
    context: ToolExecutionContext,
) -> dict[str, Any]:
    db = context.db
    session = context.session
    project_id = arguments.get("project_id")
    query = select(ResumeProjectItem).where(
        ResumeProjectItem.user_id == session.user_id,
        ResumeProjectItem.resume_version_id == session.resume_version_id,
    )
    if project_id:
        query = query.where(ResumeProjectItem.id == project_id)
    items = db.scalars(query.order_by(ResumeProjectItem.position)).all()
    if not items:
        items = _extract_projects_from_resume(session, db)
    return {
        "ok": True,
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "project_name": item.project_name,
                "responsibility": item.responsibility,
                "tech_stack": item.tech_stack,
                "achievement": item.achievement,
                "risk_points": json.loads(item.risk_points or "[]"),
            }
            for item in items
        ],
    }


def _score_answer(arguments: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
    from app.services.interview import current_open_turn, evaluate_interview_answer

    session = context.session
    turn = current_open_turn(session)
    if turn is None:
        answered = [item for item in session.turns if item.status == "answered"]
        if not answered:
            return {"ok": False, "error": "当前没有可评分的回答。"}
        last = answered[-1]
        return {
            "ok": True,
            "score": last.score,
            "feedback": last.feedback,
            "evidence": json.loads(last.evidence_json or "[]"),
            "facts": [],
            "inferences": [],
            "note": "该回答已完成评分，以下为最近一次评分结果。",
        }
    answer_text = str(arguments.get("answer_text") or "")
    result = evaluate_interview_answer(turn, answer_text)
    return {
        "ok": True,
        "score": result["score"],
        "feedback": result["feedback"],
        "evidence": result["evidence"],
        "facts": result["facts"],
        "inferences": result["inferences"],
    }


def _extract_projects_from_resume(
    session: InterviewSession,
    db: Session,
) -> list[ResumeProjectItem]:
    text = (session.resume_version.extracted_text or "").splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text:
        stripped = line.strip()
        if not stripped:
            continue
        if any(keyword in stripped for keyword in ["项目", "project", "Project"]):
            if current:
                blocks.append(current)
            current = [stripped]
        elif current:
            current.append(stripped)
    if current:
        blocks.append(current)

    items: list[ResumeProjectItem] = []
    for index, block in enumerate(blocks[:5]):
        snippet = "\n".join(block)[:1200]
        items.append(
            ResumeProjectItem(
                user_id=session.user_id,
                resume_version_id=session.resume_version_id,
                position=index,
                project_name=block[0][:200] if block else f"项目 {index + 1}",
                responsibility=snippet,
                tech_stack="",
                achievement="",
                risk_points="[]",
                raw_snippet=snippet,
            )
        )
    if items:
        db.add_all(items)
        db.flush()
    return items
