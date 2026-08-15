from __future__ import annotations

import httpx

from app.core.config import settings


class EmbeddingError(RuntimeError):
    """Embedding provider request or response validation failure."""


def embed_texts(texts: list[str]) -> list[list[float]]:
    api_key = settings.embedding_api_key
    if not api_key:
        raise EmbeddingError("缺少 EMBEDDING_API_KEY，无法生成 query embedding")

    base_url = settings.embedding_base_url.rstrip("/")
    payload = {"model": settings.embedding_model, "input": texts}
    try:
        with httpx.Client(timeout=settings.embedding_timeout_seconds) as client:
            response = client.post(
                f"{base_url}/embeddings",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise EmbeddingError(f"embedding 接口请求失败: {exc}") from exc

    vectors = body.get("data")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise EmbeddingError("embedding 接口返回结构不符合预期")
    result: list[list[float]] = []
    for vector_data in vectors:
        vector = vector_data.get("embedding") if isinstance(vector_data, dict) else None
        if not isinstance(vector, list) or not all(
            isinstance(value, (int, float)) for value in vector
        ):
            raise EmbeddingError("embedding 结果非法")
        result.append([float(value) for value in vector])
    return result
