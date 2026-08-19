from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentEventLog(Base):
    __tablename__ = "agent_event_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    node_name: Mapped[str | None] = mapped_column(String(120))
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    duration_ms: Mapped[float | None] = mapped_column(Float)
    token_count: Mapped[int | None]
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
