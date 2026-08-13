from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ModelProviderConfig(Base):
    __tablename__ = "model_provider_configs"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_model_provider_user_provider"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    api_key: Mapped[str] = mapped_column(String(512), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255))
    timeout_seconds: Mapped[int] = mapped_column(default=30, nullable=False)
    network_mode: Mapped[str] = mapped_column(String(30), default="auto", nullable=False)
    proxy_url: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="model_provider_configs")
