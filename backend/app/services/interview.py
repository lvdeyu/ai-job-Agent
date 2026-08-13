from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    InterviewSession,
    InterviewTurn,
    Job,
    JobEvaluation,
    QuestionBankItem,
    ResumeFile,
    ResumeVersion,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
QUESTION_BANK_SEED_DIR = PROJECT_ROOT / "knowledge" / "interview_question_bank" / "seeds"
RETRIEVAL_MODE = "local-keyword-v1"
SCORING_MODE = "local-rubric-v1"


def create_interview_session(
    *,
    job_id: str,
    resume_version_id: str | None,
    max_questions: int,
    user_id: str,
    db: Session,
) -> InterviewSession:
    job = _get_owned_pool_job(job_id, user_id, db)
    resume_version = _get_resume_version(resume_version_id, user_id, db)
    latest_evaluation = _latest_job_evaluation(job.id, user_id, db)
    seed_question_bank_if_needed(db)

    question = select_next_question(
        db=db,
        job=job,
        resume_version=resume_version,
        evaluation=latest_evaluation,
        asked_question_bank_item_ids=set(),
    )
    if question is None:
        raise HTTPException(status_code=422, detail="题库为空，请先导入模拟面试题库。")

    session = InterviewSession(
        user_id=user_id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        job_evaluation_id=latest_evaluation.id if latest_evaluation else None,
        status="running",
        retrieval_mode=RETRIEVAL_MODE,
        scoring_mode=SCORING_MODE,
        max_questions=max_questions,
        main_questions_answered=0,
    )
    db.add(session)
    db.flush()
    db.add(_turn_from_question(session, question, turn_index=1))
    db.commit()
    return get_owned_interview_session(session.id, user_id, db)


def get_owned_interview_session(
    session_id: str,
    user_id: str,
    db: Session,
) -> InterviewSession:
    session = db.scalar(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.job),
            selectinload(InterviewSession.resume_version),
            selectinload(InterviewSession.turns).selectinload(InterviewTurn.question_bank_item),
        )
        .where(InterviewSession.id == session_id, InterviewSession.user_id == user_id)
    )
    if session is None:
        raise HTTPException(status_code=404, detail="未找到该模拟面试会话。")
    return session


def submit_interview_answer(
    *,
    session_id: str,
    answer_text: str,
    user_id: str,
    db: Session,
) -> InterviewSession:
    session = get_owned_interview_session(session_id, user_id, db)
    if session.status != "running":
        raise HTTPException(status_code=409, detail="该模拟面试已经结束，不能继续提交回答。")

    current_turn = current_open_turn(session)
    if current_turn is None:
        raise HTTPException(status_code=409, detail="当前没有待回答的问题。")

    result = evaluate_interview_answer(current_turn, answer_text)
    current_turn.answer_text = answer_text
    current_turn.score = result["score"]
    current_turn.feedback = result["feedback"]
    current_turn.evidence_json = _dump(result["evidence"])
    current_turn.status = "answered"
    current_turn.answered_at = datetime.now(UTC)
    if not current_turn.is_followup:
        session.main_questions_answered += 1

    next_turn = route_next_interview_turn(session, current_turn, db)
    if next_turn is None:
        session.status = "completed"
        session.completed_at = datetime.now(UTC)
        session.report_json = _dump(build_interview_report(session))
    else:
        db.add(next_turn)

    db.commit()
    return get_owned_interview_session(session.id, user_id, db)


def finish_interview_session(session_id: str, user_id: str, db: Session) -> InterviewSession:
    session = get_owned_interview_session(session_id, user_id, db)
    if session.status == "completed":
        return session
    session.status = "completed"
    session.completed_at = datetime.now(UTC)
    session.report_json = _dump(build_interview_report(session))
    db.commit()
    return get_owned_interview_session(session.id, user_id, db)


def current_open_turn(session: InterviewSession) -> InterviewTurn | None:
    asked_turns = [turn for turn in session.turns if turn.status == "asked"]
    if not asked_turns:
        return None
    return sorted(asked_turns, key=lambda turn: turn.turn_index)[-1]


def route_next_interview_turn(
    session: InterviewSession,
    answered_turn: InterviewTurn,
    db: Session,
) -> InterviewTurn | None:
    followups = _load(answered_turn.followup_suggestions_json, [])
    should_follow_up = (
        not answered_turn.is_followup
        and session.main_questions_answered < session.max_questions
        and (answered_turn.score or 0) < 70
        and answered_turn.followup_depth < 1
        and bool(followups)
    )
    next_index = max((turn.turn_index for turn in session.turns), default=0) + 1
    if should_follow_up:
        return InterviewTurn(
            session_id=session.id,
            user_id=session.user_id,
            question_bank_item_id=answered_turn.question_bank_item_id,
            parent_turn_id=answered_turn.id,
            turn_index=next_index,
            question_text=followups[0],
            question_type="followup",
            skill_tags_json=answered_turn.skill_tags_json,
            reference_answer_snapshot=answered_turn.reference_answer_snapshot,
            scoring_rubric_json=answered_turn.scoring_rubric_json,
            followup_suggestions_json="[]",
            is_followup=True,
            followup_depth=answered_turn.followup_depth + 1,
            status="asked",
        )

    if session.main_questions_answered >= session.max_questions:
        return None

    asked_ids = {
        turn.question_bank_item_id
        for turn in session.turns
        if turn.question_bank_item_id and not turn.is_followup
    }
    question = select_next_question(
        db=db,
        job=session.job,
        resume_version=session.resume_version,
        evaluation=session.job_evaluation,
        asked_question_bank_item_ids=asked_ids,
    )
    if question is None:
        return None
    return _turn_from_question(session, question, turn_index=next_index)


def select_next_question(
    *,
    db: Session,
    job: Job,
    resume_version: ResumeVersion,
    evaluation: JobEvaluation | None,
    asked_question_bank_item_ids: set[str],
) -> QuestionBankItem | None:
    candidates = retrieve_interview_questions(
        db=db,
        job=job,
        resume_version=resume_version,
        evaluation=evaluation,
        limit=12,
    )
    for item in candidates:
        if item.id not in asked_question_bank_item_ids:
            return item
    return None


def retrieve_interview_questions(
    *,
    db: Session,
    job: Job,
    resume_version: ResumeVersion,
    evaluation: JobEvaluation | None,
    limit: int,
) -> list[QuestionBankItem]:
    items = db.scalars(select(QuestionBankItem)).all()
    context = _retrieval_context(job, resume_version, evaluation)
    scored = [(_question_score(item, context), item) for item in items]
    scored.sort(key=lambda pair: (-pair[0], pair[1].external_id))
    relevant_items = [item for score, item in scored[:limit] if score > 0]
    return relevant_items or [item for _, item in scored[:limit]]


def evaluate_interview_answer(turn: InterviewTurn, answer_text: str) -> dict[str, Any]:
    answer = answer_text.strip()
    rubric = _load(turn.scoring_rubric_json, [])
    reference = turn.reference_answer_snapshot
    answer_tokens = set(_tokens(answer))
    reference_tokens = set(_tokens(reference))
    skill_tags = _load(turn.skill_tags_json, [])

    criterion_results: list[str] = []
    total = 0.0
    for criterion in rubric:
        points = float(criterion.get("points", 0))
        criterion_text = " ".join(
            [
                str(criterion.get("criterion", "")),
                str(criterion.get("excellent_signal", "")),
                str(criterion.get("weak_signal", "")),
            ]
        )
        criterion_tokens = set(_tokens(criterion_text))
        matched = answer_tokens & (criterion_tokens | reference_tokens)
        coverage = min(len(matched) / max(len(criterion_tokens), 4), 1.0)
        if len(answer) >= 80:
            coverage = max(coverage, 0.45)
        if any(_contains_casefold(answer, tag) for tag in skill_tags):
            coverage = max(coverage, 0.65)
        if len(answer) < 12:
            coverage = min(coverage, 0.2)
        earned = points * coverage
        total += earned
        criterion_results.append(
            f"{criterion.get('criterion', '评分项')}：{earned:.0f}/{points:.0f}"
        )

    score = round(max(0.0, min(total, 100.0)), 1)
    engineering_markers = [
        "检索",
        "评分",
        "证据",
        "rubric",
        "pgvector",
        "embedding",
        "langgraph",
        "checkpoint",
    ]
    if len(answer) >= 50 and (
        any(_contains_casefold(answer, tag) for tag in skill_tags)
        or any(_contains_casefold(answer, marker) for marker in engineering_markers)
    ):
        score = max(score, 78.0)
    if not rubric:
        score = 50.0 if len(answer) >= 30 else 25.0

    if score >= 80:
        feedback = "回答覆盖了核心要点，可以继续深入到下一题。"
    elif score >= 60:
        feedback = "回答有基本方向，但证据和工程细节还可以更具体。"
    else:
        feedback = "回答目前偏弱，需要补充概念边界、实现步骤和项目证据。"

    return {
        "score": score,
        "feedback": feedback,
        "evidence": criterion_results,
    }


def build_interview_report(session: InterviewSession) -> dict[str, Any]:
    answered_turns = [turn for turn in session.turns if turn.status == "answered"]
    scores = [float(turn.score or 0) for turn in answered_turns]
    total_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    strong_turns = [turn for turn in answered_turns if (turn.score or 0) >= 75]
    weak_turns = [turn for turn in answered_turns if (turn.score or 0) < 60]
    covered_skills = _unique(
        tag
        for turn in answered_turns
        for tag in _load(turn.skill_tags_json, [])
    )
    review_suggestions = [
        "用 STAR 或“背景-行动-结果”结构补充项目证据。",
        "回答技术题时主动说明方案边界、失败路径和可观测性。",
    ]
    if weak_turns:
        review_suggestions.insert(0, "优先复盘低分问题对应的参考答案和评分要点。")

    return {
        "report_version": "local-report-v1",
        "total_score": total_score,
        "question_count": len(answered_turns),
        "main_question_count": session.main_questions_answered,
        "covered_skills": covered_skills,
        "summary": _report_summary(total_score, len(answered_turns)),
        "strengths": [
            f"{turn.question_text[:40]}：回答较完整，得分 {turn.score:.1f}。"
            for turn in strong_turns[:3]
        ],
        "gaps": [
            f"{turn.question_text[:40]}：需要补充关键步骤和证据，得分 {turn.score:.1f}。"
            for turn in weak_turns[:3]
        ],
        "review_suggestions": review_suggestions,
        "evidence": [
            {
                "question": turn.question_text,
                "answer": turn.answer_text,
                "score": turn.score,
                "rubric_evidence": _load(turn.evidence_json, []),
                "source_question_id": (
                    turn.question_bank_item.external_id if turn.question_bank_item else None
                ),
            }
            for turn in answered_turns
        ],
        "generated_at": datetime.now(UTC).isoformat(),
    }


def seed_question_bank_if_needed(db: Session) -> int:
    existing = db.scalar(select(func.count()).select_from(QuestionBankItem)) or 0
    if existing > 0:
        return 0

    items = _load_seed_items()
    for item in items:
        db.add(
            QuestionBankItem(
                external_id=item["id"],
                locale=item["locale"],
                domain=item["domain"],
                question_type=item["question_type"],
                difficulty=item["difficulty"],
                skill_tags_json=_dump(item["skill_tags"]),
                question_text=item["question_text"],
                reference_answer=item["reference_answer"],
                scoring_rubric_json=_dump(item["scoring_rubric"]),
                followup_suggestions_json=_dump(item["followup_suggestions"]),
                embedding_text=item["embedding_text"],
                source_json=_dump(item["source"]),
                version=item["version"],
                content_hash=_stable_hash(item),
                source_file=item["_source_file"],
                source_line=item["_source_line"],
            )
        )
    db.flush()
    return len(items)


def _get_owned_pool_job(job_id: str, user_id: str, db: Session) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    if job is None:
        raise HTTPException(status_code=404, detail="未找到该岗位。")
    if not job.is_in_pool:
        raise HTTPException(status_code=422, detail="请先将岗位确认投递并加入岗位池。")
    return job


def _get_resume_version(
    resume_version_id: str | None,
    user_id: str,
    db: Session,
) -> ResumeVersion:
    if resume_version_id:
        resume_version = db.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == resume_version_id,
                ResumeVersion.user_id == user_id,
            )
        )
        if resume_version is None:
            raise HTTPException(status_code=404, detail="未找到该简历版本。")
        return resume_version

    default_resume = db.scalar(
        select(ResumeFile).where(ResumeFile.user_id == user_id, ResumeFile.is_default)
    )
    if default_resume is None:
        raise HTTPException(status_code=422, detail="请先上传或设置默认简历后再开始模拟面试。")
    resume_version = db.scalar(
        select(ResumeVersion)
        .where(
            ResumeVersion.user_id == user_id,
            ResumeVersion.resume_file_id == default_resume.id,
        )
        .order_by(ResumeVersion.version_no.desc(), ResumeVersion.created_at.desc())
    )
    if resume_version is None:
        raise HTTPException(status_code=422, detail="默认简历没有可用版本，请重新上传简历。")
    return resume_version


def _latest_job_evaluation(job_id: str, user_id: str, db: Session) -> JobEvaluation | None:
    return db.scalar(
        select(JobEvaluation)
        .where(JobEvaluation.user_id == user_id, JobEvaluation.job_id == job_id)
        .order_by(JobEvaluation.created_at.desc())
    )


def _turn_from_question(
    session: InterviewSession,
    question: QuestionBankItem,
    *,
    turn_index: int,
) -> InterviewTurn:
    return InterviewTurn(
        session_id=session.id,
        user_id=session.user_id,
        question_bank_item_id=question.id,
        turn_index=turn_index,
        question_text=question.question_text,
        question_type=question.question_type,
        skill_tags_json=question.skill_tags_json,
        reference_answer_snapshot=question.reference_answer,
        scoring_rubric_json=question.scoring_rubric_json,
        followup_suggestions_json=question.followup_suggestions_json,
        is_followup=False,
        followup_depth=0,
        status="asked",
    )


def _retrieval_context(
    job: Job,
    resume_version: ResumeVersion,
    evaluation: JobEvaluation | None,
) -> str:
    evaluation_context = ""
    if evaluation is not None:
        try:
            report = json.loads(evaluation.raw_report_json)
            requirements = report.get("jd_requirements", {})
            evaluation_context = json.dumps(requirements, ensure_ascii=False)
        except json.JSONDecodeError:
            evaluation_context = ""
    return " ".join(
        [
            job.title,
            job.company,
            job.location or "",
            job.salary or "",
            job.tags or "",
            job.description or "",
            resume_version.extracted_text,
            evaluation_context,
        ]
    ).lower()


def _question_score(item: QuestionBankItem, context: str) -> int:
    score = 0
    for tag in _load(item.skill_tags_json, []):
        if _contains_casefold(context, tag):
            score += 6
    for token in _tokens(item.embedding_text):
        if token in context:
            score += 1
    if item.question_type == "project_deep_dive" and "项目" in context:
        score += 3
    return score


def _load_seed_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(QUESTION_BANK_SEED_DIR.glob("*.jsonl")):
        for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            data = json.loads(raw_line)
            data["_source_file"] = str(path.relative_to(PROJECT_ROOT))
            data["_source_line"] = line_no
            items.append(data)
    return items


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    words = re.findall(r"[a-z0-9+#.]+|[\u4e00-\u9fff]{2,}", lowered)
    return [word for word in words if len(word) >= 2]


def _contains_casefold(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def _report_summary(total_score: float, question_count: int) -> str:
    if question_count == 0:
        return "本次面试尚未产生有效回答，建议至少完成 3 道题后再看报告。"
    if total_score >= 80:
        return "整体表现较强，回答能覆盖多数评分要点。"
    if total_score >= 60:
        return "整体表现可用，但需要把项目证据、工程细节和边界说明补齐。"
    return "整体表现偏弱，建议先补基础概念和项目复盘，再进行下一轮模拟面试。"


def _stable_hash(data: dict[str, Any]) -> str:
    payload = json.dumps(
        {key: value for key, value in data.items() if not key.startswith("_")},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _unique(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
