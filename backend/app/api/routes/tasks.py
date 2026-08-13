from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import InterviewSession, JobCollectionSession, User
from app.schemas import TaskStatusItemResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/status", response_model=list[TaskStatusItemResponse])
def list_task_status(
    current_user: CurrentUser,
    db: DbSession,
) -> list[TaskStatusItemResponse]:
    latest_collection = db.scalar(
        select(JobCollectionSession)
        .where(JobCollectionSession.user_id == current_user.id)
        .order_by(JobCollectionSession.updated_at.desc())
    )
    latest_interview = db.scalar(
        select(InterviewSession)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.updated_at.desc())
    )
    return [
        TaskStatusItemResponse(
            name="本地任务执行器",
            status="running",
            backend="in-process",
            detail="V0.1 本地闭环使用同步 API 和浏览器扩展主动回传，暂未启动 Celery worker。",
            updated_at=None,
        ),
        TaskStatusItemResponse(
            name="Celery 异步队列",
            status="not_enabled",
            backend="celery",
            detail="计划项已在任务状态页显式展示；V0.1 本地版本不依赖 Celery 执行主链路。",
            updated_at=None,
        ),
        TaskStatusItemResponse(
            name="最近 Boss 采集",
            status=latest_collection.status if latest_collection else "no_task",
            backend="browser-extension",
            detail=(
                f"关键词：{latest_collection.keyword}，接收岗位：{latest_collection.accepted_count}"
                if latest_collection
                else "当前用户暂无采集任务。"
            ),
            updated_at=latest_collection.updated_at if latest_collection else None,
        ),
        TaskStatusItemResponse(
            name="最近模拟面试",
            status=latest_interview.status if latest_interview else "no_task",
            backend="interview-agent",
            detail=(
                f"已答主问题：{latest_interview.main_questions_answered}/{latest_interview.max_questions}"
                if latest_interview
                else "当前用户暂无模拟面试任务。"
            ),
            updated_at=latest_interview.updated_at if latest_interview else None,
        ),
    ]
