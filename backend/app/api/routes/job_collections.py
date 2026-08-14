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
from app.core.config import settings
from app.db.session import get_db
from app.models import Job, JobCollectionSession, JobCollectionSessionJob, User
from app.schemas import (
    CreateJobCollectionSessionRequest,
    DeleteJobCollectionSessionsRequest,
    DeleteJobCollectionSessionsResponse,
    JobCollectionAdapterStatusResponse,
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

FAILURE_STATUSES = {
    "failed",
    "AUTH_REQUIRED",
    "CAPTCHA_REQUIRED",
    "RATE_LIMITED",
    "SOURCE_CHANGED",
    "NO_RESULT",
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
        application_status=job.application_status,
        applied_at=job.applied_at,
        application_resume_version_id=job.application_resume_version_id,
        application_resume_title=(
            job.application_resume_version.title if job.application_resume_version else None
        ),
        contact_name=job.contact_name,
        notes=job.notes,
        status_changed_at=job.status_changed_at,
        has_interviewed=False,
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
        adapter_name=session.adapter_name,
        adapter_enabled_snapshot=session.adapter_enabled_snapshot,
        extension_version=session.extension_version,
        page_limit=session.page_limit,
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
        adapter_name=session.adapter_name,
        adapter_enabled_snapshot=session.adapter_enabled_snapshot,
        extension_version=session.extension_version,
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


@router.get("/adapter-status", response_model=JobCollectionAdapterStatusResponse)
def get_collection_adapter_status(
    current_user: CurrentUser,
) -> JobCollectionAdapterStatusResponse:
    return JobCollectionAdapterStatusResponse(
        name="boss-browser",
        enabled=settings.boss_adapter_enabled,
        min_extension_version=settings.boss_adapter_min_extension_version,
        max_page_limit=settings.boss_collection_page_limit,
        rate_limit_window_seconds=settings.boss_collection_rate_limit_window_seconds,
        rate_limit_max_sessions=settings.boss_collection_rate_limit_max_sessions,
        detail=(
            "Boss 浏览器扩展采集适配器可用。"
            if settings.boss_adapter_enabled
            else "Boss 浏览器扩展采集适配器已停用，暂不允许创建采集任务。"
        ),
    )


@router.post("/sessions", response_model=JobCollectionSessionResponse)
def create_collection_session(
    payload: CreateJobCollectionSessionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> JobCollectionSessionResponse:
    now = datetime.now(UTC)
    if not settings.boss_adapter_enabled:
        raise HTTPException(status_code=503, detail="Boss 采集适配器已停用，暂不允许创建采集任务。")
    if payload.extension_version and _version_lt(
        payload.extension_version,
        settings.boss_adapter_min_extension_version,
    ):
        raise HTTPException(
            status_code=426,
            detail=(
                "浏览器扩展版本过旧，请升级到 "
                f"{settings.boss_adapter_min_extension_version} 或更高版本。"
            ),
        )
    if payload.idempotency_key:
        existing = db.scalar(
            select(JobCollectionSession).where(
                JobCollectionSession.user_id == current_user.id,
                JobCollectionSession.idempotency_key == payload.idempotency_key,
            )
        )
        if existing is not None:
            return _session_response(existing)

    window_start = now - timedelta(seconds=settings.boss_collection_rate_limit_window_seconds)
    recent_count = db.scalar(
        select(func.count())
        .select_from(JobCollectionSession)
        .where(
            JobCollectionSession.user_id == current_user.id,
            JobCollectionSession.created_at >= window_start,
        )
    )
    if (recent_count or 0) >= settings.boss_collection_rate_limit_max_sessions:
        raise HTTPException(status_code=429, detail="Boss 采集过于频繁，请稍后再试。")

    session = JobCollectionSession(
        user_id=current_user.id,
        keyword=payload.keyword,
        city=payload.city,
        work_type=payload.work_type,
        limit=payload.limit,
        status="created",
        collection_token=secrets.token_urlsafe(32),
        token_expires_at=now + timedelta(minutes=15),
        idempotency_key=payload.idempotency_key,
        extension_version=payload.extension_version,
        adapter_name="boss-browser",
        adapter_enabled_snapshot=settings.boss_adapter_enabled,
        page_limit=settings.boss_collection_page_limit,
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


@router.delete("/sessions", response_model=DeleteJobCollectionSessionsResponse)
def delete_collection_sessions(
    payload: DeleteJobCollectionSessionsRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> DeleteJobCollectionSessionsResponse:
    sessions = db.scalars(
        select(JobCollectionSession).where(
            JobCollectionSession.id.in_(payload.session_ids),
            JobCollectionSession.user_id == current_user.id,
        )
    ).all()
    deleted_count = _delete_collection_sessions(sessions, db)
    return DeleteJobCollectionSessionsResponse(deleted_count=deleted_count)


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

    _delete_collection_sessions([session], db)


def _delete_collection_sessions(sessions: list[JobCollectionSession], db: Session) -> int:
    if not sessions:
        return 0

    session_ids = [session.id for session in sessions]
    db.execute(
        update(Job)
        .where(Job.collection_session_id.in_(session_ids))
        .values(collection_session_id=None)
    )
    for session in sessions:
        db.delete(session)
    db.commit()
    return len(sessions)


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
    if (
        payload.idempotency_key
        and session.idempotency_key
        and payload.idempotency_key != session.idempotency_key
    ):
        raise HTTPException(status_code=409, detail="采集幂等键与会话不匹配，请重新创建采集任务。")
    if session.status != "created":
        return SubmitCollectedJobsResponse(
            accepted=session.accepted_count,
            created=session.created_count,
            duplicated=session.duplicated_count,
            filtered=session.filtered_count,
            status=session.status,
        )

    if payload.status in FAILURE_STATUSES or payload.error_code in {
        "AUTH_REQUIRED",
        "CAPTCHA_REQUIRED",
        "RATE_LIMITED",
        "SOURCE_CHANGED",
    }:
        session.status = payload.error_code or payload.status
        session.error_code = payload.error_code or payload.status
        session.error_message = payload.error_message or _collection_error_message(session.status)
        session.accepted_count = min(len(payload.jobs), session.limit)
        session.created_count = 0
        session.duplicated_count = 0
        session.filtered_count = 0
        session.extension_version = payload.extension_version or session.extension_version
        db.commit()
        return SubmitCollectedJobsResponse(
            accepted=session.accepted_count,
            created=0,
            duplicated=0,
            filtered=0,
            status=session.status,
        )

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
            item.description,
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
    description: str | None,
    source_job_id: str | None,
) -> str:
    if source_job_id:
        raw = "|".join([user_id, "boss", source_job_id.strip().lower()])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    raw = "|".join(
        [
            user_id,
            title.strip().lower(),
            company.strip().lower(),
            location or "",
            _jd_summary_for_fingerprint(description),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _jd_summary_for_fingerprint(value: str | None) -> str:
    return (value or "").strip().lower()[:200]


def _collection_error_message(status: str) -> str:
    messages = {
        "AUTH_REQUIRED": "Boss 当前未登录或登录已失效，请在 Boss 页面手动登录后重新采集。",
        "CAPTCHA_REQUIRED": "Boss 要求安全验证，请手动完成后再重新采集。",
        "RATE_LIMITED": "Boss 采集过于频繁，请稍后再试。",
        "SOURCE_CHANGED": "Boss 页面结构可能已变化，本次采集已停止，未写入不完整岗位。",
        "NO_RESULT": "当前 Boss 页面没有可采集的有效岗位。",
    }
    return messages.get(status, "本次采集失败，已有岗位和评测数据不会受到影响。")


def _version_lt(left: str, right: str) -> bool:
    def parse(value: str) -> tuple[int, ...]:
        parts = re.findall(r"\d+", value)
        return tuple(int(part) for part in parts[:3]) or (0,)

    return parse(left) < parse(right)


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
