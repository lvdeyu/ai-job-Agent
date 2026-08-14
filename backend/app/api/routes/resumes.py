from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import Job, JobEvaluation, ResumeFile, ResumeVersion, User
from app.schemas import (
    CreateJobSpecificResumeVersionRequest,
    ResumeFileResponse,
    ResumeVersionResponse,
    UpdateResumeVersionRequest,
)
from app.services.resume_parser import (
    SUPPORTED_RESUME_EXTENSIONS,
    compact_text,
    extract_resume_text,
)

router = APIRouter(prefix="/resumes", tags=["resumes"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
ResumeUpload = Annotated[UploadFile, File(...)]

MAX_RESUME_SIZE = 8 * 1024 * 1024


def _safe_filename(filename: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._\-\u4e00-\u9fa5]", "_", filename)[:120]


@router.get("", response_model=list[ResumeFileResponse])
def list_resumes(
    current_user: CurrentUser,
    db: DbSession,
) -> list[ResumeFile]:
    return list(
        db.scalars(
            select(ResumeFile)
            .options(selectinload(ResumeFile.versions))
            .where(ResumeFile.user_id == current_user.id)
            .order_by(ResumeFile.created_at.desc())
        ).all()
    )


@router.get("/{resume_id}", response_model=ResumeFileResponse)
def get_resume(
    resume_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> ResumeFile:
    resume = db.scalar(
        select(ResumeFile)
        .options(selectinload(ResumeFile.versions))
        .where(ResumeFile.id == resume_id, ResumeFile.user_id == current_user.id)
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="未找到该简历。")
    return resume


@router.post(
    "/versions/job-specific",
    response_model=ResumeVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job_specific_resume_version(
    payload: CreateJobSpecificResumeVersionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ResumeVersion:
    job = db.scalar(select(Job).where(Job.id == payload.job_id, Job.user_id == current_user.id))
    if job is None:
        raise HTTPException(status_code=404, detail="未找到该岗位。")
    if not job.is_in_pool:
        raise HTTPException(
            status_code=422,
            detail="请先确认投递并加入岗位池后再复制岗位专属简历。",
        )

    source_version = _get_owned_resume_version(
        payload.source_resume_version_id,
        current_user.id,
        db,
    )
    next_version_no = _next_resume_version_no(source_version.resume_file_id, current_user.id, db)
    default_title = f"{job.company} {job.title} 专属 v{next_version_no}"
    version = ResumeVersion(
        user_id=current_user.id,
        resume_file_id=source_version.resume_file_id,
        source_version_id=source_version.id,
        job_id=job.id,
        source_type="job_copy",
        version_no=next_version_no,
        title=(payload.title or default_title)[:120],
        extracted_text=source_version.extracted_text,
        structured_summary=source_version.structured_summary,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.post(
    "/jobs/{job_id}/upload",
    response_model=ResumeVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_job_resume(
    job_id: str,
    file: ResumeUpload,
    current_user: CurrentUser,
    db: DbSession,
) -> ResumeVersion:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == current_user.id))
    if job is None:
        raise HTTPException(status_code=404, detail="未找到该岗位。")
    if not job.is_in_pool:
        raise HTTPException(status_code=422, detail="请先确认投递并加入岗位池后再上传岗位简历。")

    upload = await _save_and_extract_resume(file, current_user)
    resume = ResumeFile(
        user_id=current_user.id,
        original_filename=upload["filename"],
        file_ext=upload["file_ext"],
        storage_path=str(upload["storage_path"]),
        content_type=file.content_type,
        file_size=upload["file_size"],
        is_default=False,
    )
    db.add(resume)
    db.flush()
    version = ResumeVersion(
        user_id=current_user.id,
        resume_file_id=resume.id,
        job_id=job.id,
        source_type="job_upload",
        version_no=1,
        title=f"{job.company} {job.title} - {Path(upload['filename']).stem}"[:120],
        extracted_text=upload["extracted_text"],
        structured_summary=None,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.patch("/versions/{version_id}", response_model=ResumeVersionResponse)
def update_resume_version(
    version_id: str,
    payload: UpdateResumeVersionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ResumeVersion:
    version = db.scalar(
        select(ResumeVersion).where(
            ResumeVersion.id == version_id,
            ResumeVersion.user_id == current_user.id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="未找到该简历版本。")
    if version.source_type != "job_copy":
        raise HTTPException(
            status_code=422,
            detail="只能编辑岗位专属简历版本，原始上传版本不会被覆盖。",
        )

    if payload.title is not None:
        version.title = payload.title
    version.extracted_text = compact_text(payload.extracted_text)
    if not version.extracted_text:
        raise HTTPException(status_code=422, detail="简历版本内容不能为空。")
    db.commit()
    db.refresh(version)
    return version


@router.post("/upload", response_model=ResumeFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: ResumeUpload,
    current_user: CurrentUser,
    db: DbSession,
) -> ResumeFile:
    upload = await _save_and_extract_resume(file, current_user)

    has_default = db.scalar(
        select(ResumeFile.id).where(ResumeFile.user_id == current_user.id, ResumeFile.is_default)
    )
    resume = ResumeFile(
        user_id=current_user.id,
        original_filename=upload["filename"],
        file_ext=upload["file_ext"],
        storage_path=str(upload["storage_path"]),
        content_type=file.content_type,
        file_size=upload["file_size"],
        is_default=has_default is None,
    )
    db.add(resume)
    db.flush()
    version = ResumeVersion(
        user_id=current_user.id,
        resume_file_id=resume.id,
        version_no=1,
        title=f"{Path(upload['filename']).stem} v1",
        extracted_text=upload["extracted_text"],
        structured_summary=None,
    )
    db.add(version)
    db.commit()
    return get_resume(resume.id, current_user, db)


@router.post("/{resume_id}/set-default", response_model=ResumeFileResponse)
def set_default_resume(
    resume_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> ResumeFile:
    resume = db.scalar(
        select(ResumeFile).where(ResumeFile.id == resume_id, ResumeFile.user_id == current_user.id)
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="未找到该简历。")
    db.execute(
        update(ResumeFile).where(ResumeFile.user_id == current_user.id).values(is_default=False)
    )
    resume.is_default = True
    db.commit()
    return get_resume(resume.id, current_user, db)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    resume = db.scalar(
        select(ResumeFile).where(ResumeFile.id == resume_id, ResumeFile.user_id == current_user.id)
    )
    if resume is None:
        raise HTTPException(status_code=404, detail="未找到该简历。")

    replacement_default = None
    if resume.is_default:
        replacement_default = db.scalar(
            select(ResumeFile)
            .where(ResumeFile.user_id == current_user.id, ResumeFile.id != resume.id)
            .order_by(ResumeFile.created_at.desc())
        )

    version_ids = db.scalars(
        select(ResumeVersion.id).where(
            ResumeVersion.user_id == current_user.id,
            ResumeVersion.resume_file_id == resume.id,
        )
    ).all()
    if version_ids:
        db.execute(delete(JobEvaluation).where(JobEvaluation.resume_version_id.in_(version_ids)))
        db.execute(delete(ResumeVersion).where(ResumeVersion.id.in_(version_ids)))

    storage_path = Path(resume.storage_path)
    db.delete(resume)
    if replacement_default is not None:
        replacement_default.is_default = True
    db.commit()
    storage_path.unlink(missing_ok=True)


async def _save_and_extract_resume(file: UploadFile, current_user: User) -> dict[str, object]:
    filename = file.filename or "resume"
    file_ext = Path(filename).suffix.lower()
    if file_ext not in SUPPORTED_RESUME_EXTENSIONS:
        raise HTTPException(status_code=422, detail="仅支持 .docx、.md、.pdf 简历文件。")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="上传文件不能为空。")
    if len(content) > MAX_RESUME_SIZE:
        raise HTTPException(status_code=413, detail="简历文件不能超过 8MB。")

    user_dir = Path(settings.resume_storage_dir).resolve() / current_user.id
    user_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    storage_path = user_dir / f"{Path(safe_name).stem}_{len(content)}{file_ext}"
    storage_path.write_bytes(content)

    try:
        extracted_text = compact_text(extract_resume_text(storage_path, file_ext))
    except Exception as exc:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"简历解析失败：{exc}") from exc
    if not extracted_text:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="未能从简历中提取到文本。扫描版 PDF 暂不支持。")

    return {
        "filename": filename,
        "file_ext": file_ext,
        "storage_path": storage_path,
        "file_size": len(content),
        "extracted_text": extracted_text,
    }


def _get_owned_resume_version(
    resume_version_id: str | None,
    user_id: str,
    db: Session,
) -> ResumeVersion:
    if resume_version_id:
        version = db.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == resume_version_id,
                ResumeVersion.user_id == user_id,
            )
        )
        if version is None:
            raise HTTPException(status_code=404, detail="未找到该简历版本。")
        return version

    default_resume = db.scalar(
        select(ResumeFile).where(ResumeFile.user_id == user_id, ResumeFile.is_default)
    )
    if default_resume is None:
        raise HTTPException(status_code=422, detail="请先上传或设置默认简历。")
    version = db.scalar(
        select(ResumeVersion)
        .where(ResumeVersion.user_id == user_id, ResumeVersion.resume_file_id == default_resume.id)
        .order_by(ResumeVersion.version_no.desc(), ResumeVersion.created_at.desc())
    )
    if version is None:
        raise HTTPException(status_code=422, detail="默认简历没有可用版本，请重新上传简历。")
    return version


def _next_resume_version_no(resume_file_id: str, user_id: str, db: Session) -> int:
    max_version_no = db.scalar(
        select(func.max(ResumeVersion.version_no)).where(
            ResumeVersion.user_id == user_id,
            ResumeVersion.resume_file_id == resume_file_id,
        )
    )
    return (max_version_no or 0) + 1
