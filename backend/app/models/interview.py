from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuestionBankItem(Base):
    __tablename__ = "question_bank_items"
    __table_args__ = (UniqueConstraint("external_id", name="uq_question_bank_external_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(20), nullable=False, default="zh-CN")
    domain: Mapped[str] = mapped_column(String(80), nullable=False)
    question_type: Mapped[str] = mapped_column(String(40), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    skill_tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rubric_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    followup_suggestions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    source_file: Mapped[str] = mapped_column(String(500), nullable=False)
    source_line: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    turns = relationship("InterviewTurn", back_populates="question_bank_item")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    resume_version_id: Mapped[str] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_evaluation_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_evaluations.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    retrieval_mode: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="local-keyword-v1",
    )
    scoring_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="local-rubric-v1")
    max_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    main_questions_answered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job = relationship("Job")
    resume_version = relationship("ResumeVersion")
    job_evaluation = relationship("JobEvaluation")
    turns = relationship(
        "InterviewTurn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="InterviewTurn.created_at",
    )


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_bank_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_bank_items.id", ondelete="SET NULL")
    )
    parent_turn_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_turns.id", ondelete="SET NULL")
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(40), nullable=False)
    skill_tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    reference_answer_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rubric_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    followup_suggestions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_followup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    followup_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answer_text: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None]
    feedback: Mapped[str | None] = mapped_column(Text)
    evidence_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="asked")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session = relationship("InterviewSession", back_populates="turns")
    question_bank_item = relationship("QuestionBankItem", back_populates="turns")
