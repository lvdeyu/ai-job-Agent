from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    InterviewSession,
    InterviewTurn,
    Job,
    JobEvaluation,
    ModelProviderConfig,
    ResumeFile,
    ResumeVersion,
    User,
    UserProfile,
)
from app.schemas import (
    CreateJobEvaluationRequest,
    DeleteJobPoolJobsRequest,
    DeleteJobPoolJobsResponse,
    JobEvaluationResponse,
    JobResponse,
    UpdateJobPoolItemRequest,
)
from app.services.job_evaluation import build_job_evaluation_report

router = APIRouter(prefix="/jobs", tags=["jobs"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[JobResponse])
def list_jobs(
    current_user: CurrentUser,
    db: DbSession,
) -> list[JobResponse]:
    jobs = db.scalars(
        select(Job).where(Job.user_id == current_user.id).order_by(Job.created_at.desc())
    )
    return [_job_response(job, db) for job in jobs]


@router.get("/pool", response_model=list[JobResponse])
def list_job_pool(
    current_user: CurrentUser,
    db: DbSession,
    status: str | None = None,
    keyword: str | None = None,
    company: str | None = None,
    city: str | None = None,
) -> list[JobResponse]:
    query = select(Job).where(Job.user_id == current_user.id, Job.is_in_pool)
    if status:
        query = query.where(Job.application_status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.where(
            (Job.title.ilike(like))
            | (Job.company.ilike(like))
            | (Job.location.ilike(like))
            | (Job.tags.ilike(like))
            | (Job.description.ilike(like))
        )
    if company:
        query = query.where(Job.company.ilike(f"%{company.strip()}%"))
    if city:
        query = query.where(Job.location.ilike(f"%{city.strip()}%"))
    jobs = db.scalars(query.order_by(Job.updated_at.desc(), Job.created_at.desc()))
    return [_job_response(job, db) for job in jobs]


@router.delete("/pool", response_model=DeleteJobPoolJobsResponse)
def remove_jobs_from_pool(
    payload: DeleteJobPoolJobsRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> DeleteJobPoolJobsResponse:
    owned_job_ids = db.scalars(
        select(Job.id).where(
            Job.user_id == current_user.id,
            Job.is_in_pool,
            Job.id.in_(payload.job_ids),
        )
    ).all()
    if owned_job_ids:
        db.execute(
            update(Job)
            .where(Job.user_id == current_user.id, Job.id.in_(owned_job_ids))
            .values(
                is_in_pool=False,
                application_status="ARCHIVED",
                status_changed_at=datetime.now(UTC),
            )
        )
        db.commit()
    return DeleteJobPoolJobsResponse(removed_count=len(owned_job_ids))


@router.post("/{job_id}/pool", response_model=JobResponse)
def add_job_to_pool(
    job_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> JobResponse:
    job = _get_owned_job(job_id, current_user.id, db)
    now = datetime.now(UTC)
    if not job.is_in_pool:
        job.is_in_pool = True
        job.application_status = "CONFIRMED"
        job.status_changed_at = now
        db.commit()
        db.refresh(job)
    return _job_response(job, db)


@router.patch("/{job_id}/pool", response_model=JobResponse)
def update_job_pool_item(
    job_id: str,
    payload: UpdateJobPoolItemRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> JobResponse:
    job = _get_owned_job(job_id, current_user.id, db)
    if not job.is_in_pool:
        raise HTTPException(status_code=422, detail="请先将岗位加入岗位池。")

    if payload.application_resume_version_id:
        resume_version = db.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == payload.application_resume_version_id,
                ResumeVersion.user_id == current_user.id,
            )
        )
        if resume_version is None:
            raise HTTPException(status_code=404, detail="未找到该简历版本。")

    job.application_status = payload.application_status
    job.applied_at = payload.applied_at
    job.application_resume_version_id = payload.application_resume_version_id
    job.contact_name = payload.contact_name
    job.notes = payload.notes
    job.status_changed_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return _job_response(job, db)


@router.get("/{job_id}/evaluations", response_model=list[JobEvaluationResponse])
def list_job_evaluations(
    job_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> list[JobEvaluationResponse]:
    _get_owned_job(job_id, current_user.id, db)
    evaluations = db.scalars(
        select(JobEvaluation)
        .where(JobEvaluation.user_id == current_user.id, JobEvaluation.job_id == job_id)
        .order_by(JobEvaluation.created_at.desc())
    ).all()
    return [_evaluation_response(evaluation, db) for evaluation in evaluations]


@router.post("/{job_id}/evaluations", response_model=JobEvaluationResponse)
def create_job_evaluation(
    job_id: str,
    payload: CreateJobEvaluationRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> JobEvaluationResponse:
    job = _get_owned_job(job_id, current_user.id, db)
    resume_version = _get_resume_version(payload.resume_version_id, current_user.id, db, job.id)
    model_provider = _get_model_provider(payload.model_provider_id, current_user.id, db)
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == current_user.id))

    report = build_job_evaluation_report(job, resume_version, profile)
    evaluation = JobEvaluation(
        user_id=current_user.id,
        job_id=job.id,
        resume_version_id=resume_version.id,
        model_provider_id=model_provider.id if model_provider else None,
        framework_version=report["framework_version"],
        prompt_version=report["prompt_version"],
        output_schema_version=report["output_schema_version"],
        raw_weighted_score=report["raw_weighted_score"],
        final_score=report["final_score"],
        recommendation=report["recommendation"],
        one_sentence_reason=report["one_sentence_reason"],
        language_gate_triggered=report["language_gate_triggered"],
        dealbreakers_hit=_dump(report["dealbreakers_hit"]),
        dimensions_json=_dump(report["dimensions"]),
        highlights_json=_dump(report["highlights"]),
        risks_and_gaps_json=_dump(report["risks_and_gaps"]),
        salary_benchmark_json=_dump(report["salary_benchmark"]),
        evidence_json=_dump(report["evidence"]),
        resume_focus_suggestions_json=_dump(report["resume_focus_suggestions"]),
        honest_gap_statements_json=_dump(report["honest_gap_statements"]),
        raw_report_json=_dump(report),
    )
    db.add(evaluation)
    if job.is_in_pool and job.application_status in {"NEW", "CONFIRMED"}:
        job.application_status = "SCORED"
        job.status_changed_at = datetime.now(UTC)
    db.commit()
    db.refresh(evaluation)
    return _evaluation_response(evaluation, db)


def _get_owned_job(job_id: str, user_id: str, db: Session) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    if job is None:
        raise HTTPException(status_code=404, detail="未找到该岗位。")
    return job


def _job_response(job: Job, db: Session) -> JobResponse:
    has_interviewed = (
        db.scalar(
            select(InterviewTurn.id)
            .join(InterviewSession, InterviewTurn.session_id == InterviewSession.id)
            .where(
                InterviewSession.user_id == job.user_id,
                InterviewSession.job_id == job.id,
                InterviewTurn.status == "answered",
            )
            .limit(1)
        )
        is not None
    )
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
        has_interviewed=has_interviewed,
        created_at=job.created_at,
    )


def _get_resume_version(
    resume_version_id: str | None,
    user_id: str,
    db: Session,
    job_id: str | None = None,
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

    if job_id:
        job_resume_version = db.scalar(
            select(ResumeVersion)
            .where(
                ResumeVersion.user_id == user_id,
                ResumeVersion.job_id == job_id,
                ResumeVersion.source_type.in_(["job_upload", "job_copy"]),
            )
            .order_by(ResumeVersion.created_at.desc(), ResumeVersion.version_no.desc())
        )
        if job_resume_version is not None:
            return job_resume_version

    default_resume = db.scalar(
        select(ResumeFile).where(ResumeFile.user_id == user_id, ResumeFile.is_default)
    )
    if default_resume is None:
        raise HTTPException(status_code=422, detail="请先上传或设置默认简历后再进行 AI 测评。")
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


def _get_model_provider(
    model_provider_id: str | None,
    user_id: str,
    db: Session,
) -> ModelProviderConfig | None:
    if model_provider_id:
        model_provider = db.scalar(
            select(ModelProviderConfig).where(
                ModelProviderConfig.id == model_provider_id,
                ModelProviderConfig.user_id == user_id,
            )
        )
        if model_provider is None:
            raise HTTPException(status_code=404, detail="未找到该模型配置。")
        return model_provider
    return db.scalar(
        select(ModelProviderConfig)
        .where(ModelProviderConfig.user_id == user_id)
        .order_by(ModelProviderConfig.updated_at.desc())
    )


def _evaluation_response(evaluation: JobEvaluation, db: Session) -> JobEvaluationResponse:
    resume_version = db.scalar(
        select(ResumeVersion).where(ResumeVersion.id == evaluation.resume_version_id)
    )
    raw_report = _load(evaluation.raw_report_json, {})
    return JobEvaluationResponse(
        id=evaluation.id,
        job_id=evaluation.job_id,
        resume_version_id=evaluation.resume_version_id,
        resume_title=resume_version.title if resume_version else None,
        resume_source_type=resume_version.source_type if resume_version else None,
        model_provider_id=evaluation.model_provider_id,
        framework_version=evaluation.framework_version,
        prompt_version=evaluation.prompt_version,
        output_schema_version=evaluation.output_schema_version,
        raw_weighted_score=evaluation.raw_weighted_score,
        final_score=evaluation.final_score,
        recommendation=evaluation.recommendation,
        one_sentence_reason=evaluation.one_sentence_reason,
        language_gate_triggered=evaluation.language_gate_triggered,
        dealbreakers_hit=_load(evaluation.dealbreakers_hit, []),
        dimensions=_load(evaluation.dimensions_json, {}),
        highlights=_load(evaluation.highlights_json, []),
        risks_and_gaps=_load(evaluation.risks_and_gaps_json, []),
        jd_requirements=raw_report.get("jd_requirements", {}),
        salary_benchmark=_load(evaluation.salary_benchmark_json, {}),
        evidence=_load(evaluation.evidence_json, []),
        resume_focus_suggestions=_load(evaluation.resume_focus_suggestions_json, []),
        honest_gap_statements=_load(evaluation.honest_gap_statements_json, []),
        created_at=evaluation.created_at,
    )


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
