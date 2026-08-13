from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, UserProfile
from app.schemas import ProfileRequest, ProfileResponse

router = APIRouter(prefix="/profile", tags=["profile"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=ProfileResponse | None)
def get_profile(
    current_user: CurrentUser,
    db: DbSession,
) -> UserProfile | None:
    return db.scalar(select(UserProfile).where(UserProfile.user_id == current_user.id))


@router.put("", response_model=ProfileResponse)
def upsert_profile(
    payload: ProfileRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> UserProfile:
    if payload.salary_min and payload.salary_max and payload.salary_min > payload.salary_max:
        raise HTTPException(status_code=422, detail="最低薪资不能高于最高薪资。")
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == current_user.id))
    if profile is None:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
