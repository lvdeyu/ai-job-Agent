from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Job, JobCollectionSession, JobCollectionSessionJob, User
from app.schemas import (
    CreateJobCollectionSessionRequest,
    JobCollectionSessionListResponse,
    JobCollectionSessionResponse,
    JobCollectionSessionSummaryResponse,
    JobResponse,
    SubmitCollectedJobsRequest,
    SubmitCollectedJobsResponse,
)
from app.services.boss_search import build_boss_search_url

router = APIRouter(prefix="/job-collections", tags=["job-collections"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]

_KEYWORD_ALIASES = {
    "agent": ["agent", "ai agent", "智能体", "大模型应用", "ai应用", "ai 应用", "llm"],
    "ai": ["ai", "aigc", "人工智能", "大模型", "llm", "机器学习", "深度学习", "算法"],
    "python": ["python"],
    "java": ["java", "spring", "springboot", "spring boot"],
}


def _job_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        salary=job.salary,
        experience=job.experience,
        education=job.education,
        tags=job.tags,
        job_url=job.job_url,
        description=job.description,
        is_in_pool=job.is_in_pool,
        created_at=job.created_at,
    )


def _session_response(session: JobCollectionSession) -> JobCollectionSessionResponse:
    return JobCollectionSessionResponse(
        id=session.id,
        keyword=session.keyword,
        city=session.city,
        work_type=session.work_type,
        limit=session.limit,
        status=session.status,
        collection_token=session.collection_token,
        token_expires_at=session.token_expires_at,
        boss_search_url=build_boss_search_url(session.keyword, session.city, session.work_type),
        error_code=session.error_code,
        error_message=session.error_message,
        accepted_count=session.accepted_count,
        created_count=session.created_count,
        duplicated_count=session.duplicated_count,
        filtered_count=session.filtered_count,
        jobs=[_job_response(link.job) for link in session.job_links],
    )


def _session_summary_response(session: JobCollectionSession) -> JobCollectionSessionSummaryResponse:
    return JobCollectionSessionSummaryResponse(
        id=session.id,
        keyword=session.keyword,
        city=session.city,
        work_type=session.work_type,
        limit=session.limit,
        status=session.status,
        boss_search_url=build_boss_search_url(session.keyword, session.city, session.work_type),
        error_code=session.error_code,
        error_message=session.error_message,
        accepted_count=session.accepted_count,
        created_count=session.created_count,
        duplicated_count=session.duplicated_count,
        filtered_count=session.filtered_count,
        job_count=len(session.job_links),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.post("/sessions", response_model=JobCollectionSessionResponse)
def create_collection_session(
    payload: CreateJobCollectionSessionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> JobCollectionSessionResponse:
    now = datetime.now(UTC)
    session = JobCollectionSession(
        user_id=current_user.id,
        keyword=payload.keyword,
        city=payload.city,
        work_type=payload.work_type,
        limit=payload.limit,
        status="created",
        collection_token=secrets.token_urlsafe(32),
        token_expires_at=now + timedelta(minutes=15),
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_response(session)


@router.get("/sessions", response_model=JobCollectionSessionListResponse)
def list_collection_sessions(
    current_user: CurrentUser,
    db: DbSession,
    page: int = 1,
    page_size: int = 10,
) -> JobCollectionSessionListResponse:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    total = db.scalar(
        select(func.count())
        .select_from(JobCollectionSession)
        .where(JobCollectionSession.user_id == current_user.id)
    )
    sessions = db.scalars(
        select(JobCollectionSession)
        .options(
            selectinload(JobCollectionSession.job_links).selectinload(
                JobCollectionSessionJob.job
            )
        )
        .where(JobCollectionSession.user_id == current_user.id)
        .order_by(JobCollectionSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return JobCollectionSessionListResponse(
        items=[_session_summary_response(session) for session in sessions],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/sessions/{session_id}", response_model=JobCollectionSessionResponse)
def get_collection_session(
    session_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> JobCollectionSessionResponse:
    session = db.scalar(
        select(JobCollectionSession)
        .options(
            selectinload(JobCollectionSession.job_links).selectinload(
                JobCollectionSessionJob.job
            )
        )
        .where(
            JobCollectionSession.id == session_id,
            JobCollectionSession.user_id == current_user.id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="未找到该采集会话。")
    return _session_response(session)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_collection_session(
    session_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    session = db.scalar(
        select(JobCollectionSession).where(
            JobCollectionSession.id == session_id,
            JobCollectionSession.user_id == current_user.id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="未找到该搜索历史。")

    db.execute(
        update(Job)
        .where(Job.collection_session_id == session.id)
        .values(collection_session_id=None)
    )
    db.delete(session)
    db.commit()


@router.post("/sessions/{session_id}/jobs", response_model=SubmitCollectedJobsResponse)
def submit_collected_jobs(
    session_id: str,
    payload: SubmitCollectedJobsRequest,
    db: DbSession,
) -> SubmitCollectedJobsResponse:
    session = db.scalar(
        select(JobCollectionSession).where(
            JobCollectionSession.id == session_id,
            JobCollectionSession.collection_token == payload.collection_token,
        )
    )
    if session is None:
        raise HTTPException(status_code=401, detail="采集 Token 无效。")
    if session.token_expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise HTTPException(status_code=401, detail="采集 Token 已过期，请重新创建采集任务。")

    created = 0
    duplicated = 0
    filtered = 0
    accepted = min(len(payload.jobs), session.limit)
    linked_job_ids = set(
        db.scalars(
            select(JobCollectionSessionJob.job_id).where(
                JobCollectionSessionJob.session_id == session.id
            )
        ).all()
    )
    for position, item in enumerate(payload.jobs[: session.limit]):
        if not _is_relevant_to_keyword(item, session.keyword):
            filtered += 1
            continue
        if not _matches_work_type(item, session.work_type):
            filtered += 1
            continue
        fingerprint = _fingerprint(
            session.user_id,
            item.title,
            item.company,
            item.location,
            item.job_url,
            item.source_job_id,
        )
        job = db.scalar(
            select(Job).where(
                Job.user_id == session.user_id,
                Job.source_fingerprint == fingerprint,
            )
        )
        was_duplicate = job is not None
        if was_duplicate:
            duplicated += 1
        else:
            job = Job(
                user_id=session.user_id,
                collection_session_id=session.id,
                source="boss",
                source_job_id=item.source_job_id,
                source_fingerprint=fingerprint,
                title=item.title,
                company=item.company,
                location=item.location,
                salary=item.salary,
                experience=item.experience,
                education=item.education,
                tags=",".join(item.tags) if item.tags else None,
                job_url=item.job_url,
                description=item.description,
                raw_payload=json.dumps(item.model_dump(), ensure_ascii=False),
            )
            db.add(job)
            db.flush()
            created += 1

        if job.id not in linked_job_ids:
            db.add(
                JobCollectionSessionJob(
                    session_id=session.id,
                    job_id=job.id,
                    position=position,
                    was_duplicate=was_duplicate,
                )
            )
            linked_job_ids.add(job.id)

    session.status = payload.status
    session.error_code = payload.error_code
    session.error_message = payload.error_message
    session.accepted_count = accepted
    session.created_count = created
    session.duplicated_count = duplicated
    session.filtered_count = filtered
    if payload.status == "success" and created == 0 and duplicated == 0 and filtered > 0:
        session.status = "failed"
        session.error_code = "NO_RELEVANT_JOBS"
        session.error_message = (
            f"Boss 返回了 {filtered} 个岗位，但都和关键词“{session.keyword}”不够相关，已自动过滤。"
            "建议换一个更具体的关键词，或调整工作形式筛选。"
        )
    elif payload.status == "success" and created == 0 and duplicated == 0:
        session.status = "failed"
        session.error_code = "NO_JOBS_FOUND"
        session.error_message = "没有采集到岗位，请确认已登录 Boss 且搜索结果页存在可见岗位。"
    db.commit()
    return SubmitCollectedJobsResponse(
        accepted=accepted,
        created=created,
        duplicated=duplicated,
        filtered=filtered,
        status=session.status,
    )


def _fingerprint(
    user_id: str,
    title: str,
    company: str,
    location: str | None,
    job_url: str | None,
    source_job_id: str | None,
) -> str:
    raw = "|".join(
        [
            user_id,
            source_job_id or "",
            title.strip().lower(),
            company.strip().lower(),
            location or "",
            job_url or "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_relevant_to_keyword(item, keyword: str) -> bool:
    raw_tokens = _keyword_tokens(keyword)
    tokens = _expanded_keyword_tokens(keyword)
    if not tokens:
        return True
    primary_text = _job_primary_search_text(item)
    haystack = _job_search_text(item)
    if any(_token_matches(token, primary_text) for token in tokens):
        return True
    if _requires_strict_keyword_match(raw_tokens):
        matched_alias_count = sum(1 for token in tokens if _token_matches(token, haystack))
        total_occurrences = sum(_token_occurrence_count(token, haystack) for token in tokens)
        return matched_alias_count >= 2 or total_occurrences >= 2
    return any(_token_matches(token, haystack) for token in tokens)


def _matches_work_type(item, work_type: str | None) -> bool:
    if not work_type:
        return True
    haystack = _job_search_text(item)
    internship_markers = [
        "实习",
        "在校",
        "应届",
        "校招",
        "校园",
        "元/天",
        "天/周",
        "个月",
    ]
    full_time_patterns = [
        r"\d+\s*-\s*\d+\s*年",
        r"\d+\s*年以上",
        r"\d+\s*年及以上",
    ]
    full_time_markers = ["全职", "社招"]
    is_internship_like = any(marker in haystack for marker in internship_markers)
    is_clearly_full_time = any(marker in haystack for marker in full_time_markers) or any(
        re.search(pattern, haystack) for pattern in full_time_patterns
    )
    if work_type == "internship":
        return is_internship_like or not is_clearly_full_time
    if work_type == "full_time":
        return not is_internship_like
    return True


def _expanded_keyword_tokens(keyword: str) -> list[str]:
    tokens = _keyword_tokens(keyword)
    expanded: list[str] = []
    for token in tokens:
        expanded.extend(_KEYWORD_ALIASES.get(token, [token]))
    return list(dict.fromkeys(expanded))


def _keyword_tokens(keyword: str) -> list[str]:
    cleaned = keyword.lower()
    for stop_word in ["实习生", "实习", "全职", "校招", "社招", "岗位", "招聘"]:
        cleaned = cleaned.replace(stop_word, " ")
    tokens = re.findall(r"[a-z0-9+#.]+|[\u4e00-\u9fff]{2,}", cleaned)
    return [token for token in tokens if token.strip()]


def _token_matches(token: str, haystack: str) -> bool:
    if re.fullmatch(r"[a-z0-9+#.]+", token):
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack) is not None
    return token in haystack


def _token_occurrence_count(token: str, haystack: str) -> int:
    if re.fullmatch(r"[a-z0-9+#.]+", token):
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack))
    return haystack.count(token)


def _requires_strict_keyword_match(raw_tokens: list[str]) -> bool:
    strict_tokens = {"agent", "ai", "python", "java"}
    return any(token in strict_tokens for token in raw_tokens)


def _job_primary_search_text(item) -> str:
    return " ".join(
        [
            item.title or "",
            item.company or "",
            item.location or "",
            item.salary or "",
            item.experience or "",
            item.education or "",
            " ".join(item.tags or []),
        ]
    ).lower()


def _job_search_text(item) -> str:
    return " ".join(
        [
            item.title or "",
            item.company or "",
            item.location or "",
            item.salary or "",
            item.experience or "",
            item.education or "",
            " ".join(item.tags or []),
            item.description or "",
        ]
    ).lower()
