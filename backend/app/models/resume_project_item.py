from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResumeProjectItem(Base):
    __tablename__ = "resume_project_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resume_version_id: Mapped[str] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    responsibility: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tech_stack: Mapped[str] = mapped_column(Text, nullable=False, default="")
    achievement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_points: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    raw_snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
