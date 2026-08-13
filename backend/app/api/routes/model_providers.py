from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import mask_secret
from app.db.session import get_db
from app.models import ModelProviderConfig, User
from app.schemas import ConnectionTestResponse, ModelProviderRequest, ModelProviderResponse
from app.services.model_connection import test_model_connection

router = APIRouter(prefix="/model-providers", tags=["model-providers"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _to_response(config: ModelProviderConfig) -> ModelProviderResponse:
    return ModelProviderResponse(
        id=config.id,
        provider=config.provider,
        model_name=config.model_name,
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
        network_mode=config.network_mode,
        proxy_url=config.proxy_url,
        masked_api_key=mask_secret(config.api_key),
        updated_at=config.updated_at,
    )


@router.get("", response_model=list[ModelProviderResponse])
def list_model_providers(
    current_user: CurrentUser,
    db: DbSession,
) -> list[ModelProviderResponse]:
    configs = db.scalars(
        select(ModelProviderConfig)
        .where(ModelProviderConfig.user_id == current_user.id)
        .order_by(ModelProviderConfig.provider)
    ).all()
    return [_to_response(config) for config in configs]


@router.post("", response_model=ModelProviderResponse)
def upsert_model_provider(
    payload: ModelProviderRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> ModelProviderResponse:
    config = db.scalar(
        select(ModelProviderConfig).where(
            ModelProviderConfig.user_id == current_user.id,
            ModelProviderConfig.provider == payload.provider,
        )
    )
    if config is None:
        config = ModelProviderConfig(user_id=current_user.id, provider=payload.provider)
        db.add(config)
    config.api_key = payload.api_key
    config.model_name = payload.model_name
    config.base_url = str(payload.base_url) if payload.base_url else None
    config.timeout_seconds = payload.timeout_seconds
    config.network_mode = payload.network_mode
    config.proxy_url = str(payload.proxy_url) if payload.proxy_url else None
    if config.network_mode == "manual_proxy" and not config.proxy_url:
        raise HTTPException(status_code=422, detail="选择手动代理时必须填写代理地址。")
    db.commit()
    db.refresh(config)
    return _to_response(config)


@router.delete("/{config_id}", status_code=204)
def delete_model_provider(
    config_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    config = db.scalar(
        select(ModelProviderConfig).where(
            ModelProviderConfig.id == config_id,
            ModelProviderConfig.user_id == current_user.id,
        )
    )
    if config is None:
        raise HTTPException(status_code=404, detail="未找到该模型配置。")
    db.delete(config)
    db.commit()


@router.post("/{config_id}/test", response_model=ConnectionTestResponse)
async def test_provider(
    config_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> ConnectionTestResponse:
    config = db.scalar(
        select(ModelProviderConfig).where(
            ModelProviderConfig.id == config_id,
            ModelProviderConfig.user_id == current_user.id,
        )
    )
    if config is None:
        raise HTTPException(status_code=404, detail="未找到该模型配置。")
    ok, message, error_type = await test_model_connection(config)
    return ConnectionTestResponse(
        ok=ok,
        provider=config.provider,
        message=message,
        error_type=error_type,
    )
