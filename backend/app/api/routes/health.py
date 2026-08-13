from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.environment,
    )

