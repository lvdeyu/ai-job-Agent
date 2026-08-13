from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.interviews import router as interviews_router
from app.api.routes.job_collections import router as job_collections_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.model_providers import router as model_providers_router
from app.api.routes.profile import router as profile_router
from app.api.routes.resumes import router as resumes_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(auth_router, prefix=settings.api_v1_prefix)
    app.include_router(profile_router, prefix=settings.api_v1_prefix)
    app.include_router(model_providers_router, prefix=settings.api_v1_prefix)
    app.include_router(resumes_router, prefix=settings.api_v1_prefix)
    app.include_router(job_collections_router, prefix=settings.api_v1_prefix)
    app.include_router(jobs_router, prefix=settings.api_v1_prefix)
    app.include_router(interviews_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
