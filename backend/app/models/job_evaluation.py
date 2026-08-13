from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobEvaluation(Base):
    __tablename__ = "job_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    resume_version_id: Mapped[str] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_provider_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_provider_configs.id", ondelete="SET NULL")
    )
    framework_version: Mapped[str] = mapped_column(String(30), nullable=False, default="v1")
    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False, default="local-rule-v1")
    raw_weighted_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(30), nullable=False)
    one_sentence_reason: Mapped[str] = mapped_column(Text, nullable=False)
    language_gate_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dealbreakers_hit: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    dimensions_json: Mapped[str] = mapped_column(Text, nullable=False)
    highlights_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    risks_and_gaps_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    salary_benchmark_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    resume_focus_suggestions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    honest_gap_statements_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    raw_report_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="evaluations")
    resume_version = relationship("ResumeVersion")
    model_provider = relationship("ModelProviderConfig")
