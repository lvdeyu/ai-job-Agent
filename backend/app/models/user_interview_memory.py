from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserInterviewMemory(Base):
    __tablename__ = "user_interview_memory"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "skill", name="uq_user_job_skill_memory"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    skill: Mapped[str] = mapped_column(String(120), nullable=False)
    strength_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    weak_points: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    last_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
