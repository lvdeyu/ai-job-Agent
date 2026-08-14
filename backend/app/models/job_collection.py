from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobCollectionSession(Base):
    __tablename__ = "job_collection_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str | None] = mapped_column(String(80))
    work_type: Mapped[str | None] = mapped_column(String(30))
    limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="created")
    collection_token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filtered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    extension_version: Mapped[str | None] = mapped_column(String(30))
    adapter_name: Mapped[str] = mapped_column(String(50), nullable=False, default="boss-browser")
    adapter_enabled_snapshot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    page_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    created_jobs = relationship("Job", back_populates="collection_session")
    job_links = relationship(
        "JobCollectionSessionJob",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="JobCollectionSessionJob.position",
    )


class JobCollectionSessionJob(Base):
    __tablename__ = "job_collection_session_jobs"
    __table_args__ = (
        UniqueConstraint("session_id", "job_id", name="uq_job_collection_session_jobs"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("job_collection_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    was_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session = relationship("JobCollectionSession", back_populates="job_links")
    job = relationship("Job", back_populates="collection_links")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "source_fingerprint", name="uq_jobs_user_source_fp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    collection_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_collection_sessions.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="boss")
    source_job_id: Mapped[str | None] = mapped_column(String(120))
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    company: Mapped[str] = mapped_column(String(180), nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))
    salary: Mapped[str | None] = mapped_column(String(120))
    experience: Mapped[str | None] = mapped_column(String(120))
    education: Mapped[str | None] = mapped_column(String(120))
    tags: Mapped[str | None] = mapped_column(Text)
    job_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[str | None] = mapped_column(Text)
    is_in_pool: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    application_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NEW")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    application_resume_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="SET NULL")
    )
    contact_name: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    collection_session = relationship("JobCollectionSession", back_populates="created_jobs")
    collection_links = relationship(
        "JobCollectionSessionJob",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    evaluations = relationship("JobEvaluation", back_populates="job")
    application_resume_version = relationship(
        "ResumeVersion",
        foreign_keys=[application_resume_version_id],
    )
