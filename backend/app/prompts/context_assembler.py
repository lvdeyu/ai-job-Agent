from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InterviewMessage, InterviewSession, UserInterviewMemory

_JOB_CONTEXT_MAX = 1500
_RESUME_CONTEXT_MAX = 1500


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "...（已截断）"


def build_system_prompt(session: InterviewSession) -> str:
    job = session.job
    resume = session.resume_version
    evaluation = session.job_evaluation
    lines = [
        "岗位信息：",
        _truncate(
            " ".join(
                [
                    job.title or "",
                    job.company or "",
                    job.location or "",
                    job.salary or "",
                    job.tags or "",
                    job.description or "",
                ]
            ),
            _JOB_CONTEXT_MAX,
        ),
        "",
        "简历摘要：",
        _truncate(resume.extracted_text or "", _RESUME_CONTEXT_MAX),
    ]
    if evaluation is not None:
        lines.append("")
        lines.append("岗位评测摘要：")
        try:
            raw = json.loads(evaluation.raw_report_json or "{}")
            lines.append(
                _truncate(
                    " ".join(
                        [
                            f"总分 {evaluation.final_score}",
                            f"建议：{evaluation.recommendation}",
                            evaluation.one_sentence_reason or "",
                            json.dumps(raw.get("risks_and_gaps", []), ensure_ascii=False),
                        ]
                    ),
                    800,
                )
            )
        except json.JSONDecodeError:
            pass
    lines.append("")
    lines.append("面试要求：")
    lines.append(
        f"主问题上限 {session.max_questions} 道；"
        f"当前已回答主问题 {session.main_questions_answered} 道。"
    )
    return "\n".join(lines)


def messages_to_transcript(messages: list[InterviewMessage]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for message in messages[-20:]:
        result.append({"role": message.role, "content": message.content or ""})
    return result


def build_memory_prompt(db: Session, session: InterviewSession) -> str:
    memories = db.scalars(
        select(UserInterviewMemory)
        .where(
            UserInterviewMemory.user_id == session.user_id,
            UserInterviewMemory.job_id == session.job_id,
        )
        .order_by(UserInterviewMemory.updated_at.desc())
        .limit(5)
    ).all()
    if not memories:
        return ""
    lines = ["长期记忆（上次面试强弱项）："]
    for memory in memories:
        try:
            weak = json.loads(memory.weak_points or "[]")
        except json.JSONDecodeError:
            weak = []
        weak_text = "、".join(str(item) for item in weak) or "暂无备注"
        lines.append(f"- {memory.skill}（上次得分 {memory.strength_score:.1f}）：{weak_text}")
    return "\n".join(lines)


def context_summary_for_event(session: InterviewSession) -> dict[str, Any]:
    job = session.job
    return {
        "job_title": job.title,
        "company": job.company,
        "max_questions": session.max_questions,
        "main_questions_answered": session.main_questions_answered,
        "status": session.status,
    }
