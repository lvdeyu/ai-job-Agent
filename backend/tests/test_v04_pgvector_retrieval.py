from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.services.embeddings import EmbeddingError, embed_texts
from app.services.interview import (
    RETRIEVAL_MODE,
    _has_real_embeddings,
    active_retrieval_mode,
    seed_question_bank_if_needed,
)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()


def test_active_retrieval_mode_defaults_to_keyword_when_empty(db: Session) -> None:
    assert active_retrieval_mode(db) == RETRIEVAL_MODE


def test_active_retrieval_mode_uses_fallback_with_text_embeddings(db: Session) -> None:
    seeded = seed_question_bank_if_needed(db)
    assert seeded > 0
    assert active_retrieval_mode(db) == "pgvector-fallback-v1"


def test_has_real_embeddings_false_without_vector_column_data(db: Session) -> None:
    seed_question_bank_if_needed(db)
    assert _has_real_embeddings(db) is False


def test_embed_texts_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_api_key", "")
    with pytest.raises(EmbeddingError, match="EMBEDDING_API_KEY"):
        embed_texts(["test"])


def test_embed_texts_rejects_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_api_key", "sk-test")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"data": []}

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *exc: object) -> bool:
            return False

        def post(self, *args: object, **kwargs: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("app.services.embeddings.httpx.Client", FakeClient)
    with pytest.raises(EmbeddingError, match="结构不符合预期"):
        embed_texts(["test"])
