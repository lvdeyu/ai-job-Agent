from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ModelProviderConfig
from app.services.llm.llm_client import LLMClient, LLMConfig


def get_llm_client(db: Session, user_id: str) -> LLMClient | None:
    """Return the latest usable model client for the user, or None to fall back to rules."""
    config = db.scalar(
        select(ModelProviderConfig)
        .where(ModelProviderConfig.user_id == user_id)
        .order_by(ModelProviderConfig.updated_at.desc())
        .limit(1)
    )
    if config is None or not config.api_key:
        return None
    if config.api_key.startswith("sk-local-test"):
        return None
    return LLMClient(LLMConfig.from_model_provider(config))
