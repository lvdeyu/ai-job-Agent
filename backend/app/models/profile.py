from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_profiles_user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_role: Mapped[str | None] = mapped_column(String(120))
    salary_min: Mapped[int | None]
    salary_max: Mapped[int | None]
    cities: Mapped[str | None] = mapped_column(String(255))
    work_type: Mapped[str | None] = mapped_column(String(30))
    deal_breakers: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="profile")
