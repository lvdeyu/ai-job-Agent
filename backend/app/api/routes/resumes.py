from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import JobEvaluation, ResumeFile, ResumeVersion, User
from app.schemas import ResumeFileResponse
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


@router.post("/upload", response_model=ResumeFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: ResumeUpload,
    current_user: CurrentUser,
    db: DbSession,
) -> ResumeFile:
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

    has_default = db.scalar(
        select(ResumeFile.id).where(ResumeFile.user_id == current_user.id, ResumeFile.is_default)
    )
    resume = ResumeFile(
        user_id=current_user.id,
        original_filename=filename,
        file_ext=file_ext,
        storage_path=str(storage_path),
        content_type=file.content_type,
        file_size=len(content),
        is_default=has_default is None,
    )
    db.add(resume)
    db.flush()
    version = ResumeVersion(
        user_id=current_user.id,
        resume_file_id=resume.id,
        version_no=1,
        title=f"{Path(filename).stem} v1",
        extracted_text=extracted_text,
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
