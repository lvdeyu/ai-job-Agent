from __future__ import annotations

import json
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db, get_session_factory
from app.models import AgentEventLog, InterviewSession, InterviewTurn, User
from app.schemas import (
    AgentEventResponse,
    ChatMessageRequest,
    CreateInterviewSessionRequest,
    DeleteInterviewSessionsRequest,
    DeleteInterviewSessionsResponse,
    InterviewHistoryItemResponse,
    InterviewMessageResponse,
    InterviewSessionResponse,
    InterviewTurnResponse,
    SubmitInterviewAnswerRequest,
)
from app.services.interview import (
    create_interview_session,
    current_open_turn,
    finish_interview_session,
    get_owned_interview_session,
    submit_interview_answer,
)
from app.services.interview_chat import ChatTurnError, list_session_messages, run_chat_turn
from app.services.interview_graph import interview_graph_checkpoint_mode
from app.services.llm import get_llm_client

router = APIRouter(prefix="/interviews", tags=["interviews"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[InterviewSessionResponse])
def list_interviews(
    current_user: CurrentUser,
    db: DbSession,
    job_id: str | None = None,
) -> list[InterviewSessionResponse]:
    query = select(InterviewSession).where(InterviewSession.user_id == current_user.id)
    if job_id:
        query = query.where(InterviewSession.job_id == job_id)
    sessions = db.scalars(query.order_by(InterviewSession.created_at.desc())).all()
    return [
        _session_response(get_owned_interview_session(session.id, current_user.id, db), db)
        for session in sessions
    ]


@router.get("/history", response_model=list[InterviewHistoryItemResponse])
def list_interview_history(
    current_user: CurrentUser,
    db: DbSession,
) -> list[InterviewHistoryItemResponse]:
    sessions = db.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc())
    ).all()
    return [
        _history_item_response(get_owned_interview_session(session.id, current_user.id, db))
        for session in sessions
        if _answered_count(session) > 0
    ]


@router.delete("/history", response_model=DeleteInterviewSessionsResponse)
def delete_interview_history_batch(
    payload: DeleteInterviewSessionsRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> DeleteInterviewSessionsResponse:
    sessions = db.scalars(
        select(InterviewSession).where(
            InterviewSession.user_id == current_user.id,
            InterviewSession.id.in_(payload.session_ids),
        )
    ).all()
    deleted_count = _delete_sessions(sessions, db)
    return DeleteInterviewSessionsResponse(deleted_count=deleted_count)


@router.delete("/history/{session_id}", status_code=204)
def delete_interview_history(
    session_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    session = db.scalar(
        select(InterviewSession).where(
            InterviewSession.user_id == current_user.id,
            InterviewSession.id == session_id,
        )
    )
    if session is None:
        get_owned_interview_session(session_id, current_user.id, db)
    _delete_sessions([session], db)


@router.post("", response_model=InterviewSessionResponse)
def create_interview(
    payload: CreateInterviewSessionRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> InterviewSessionResponse:
    session = create_interview_session(
        job_id=payload.job_id,
        resume_version_id=payload.resume_version_id,
        max_questions=payload.max_questions,
        user_id=current_user.id,
        db=db,
    )
    return _session_response(session, db)


@router.get("/{session_id}", response_model=InterviewSessionResponse)
def get_interview(
    session_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> InterviewSessionResponse:
    return _session_response(get_owned_interview_session(session_id, current_user.id, db), db)


@router.post("/{session_id}/answers", response_model=InterviewSessionResponse)
def submit_answer(
    session_id: str,
    payload: SubmitInterviewAnswerRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> InterviewSessionResponse:
    session = submit_interview_answer(
        session_id=session_id,
        answer_text=payload.answer_text,
        user_id=current_user.id,
        db=db,
    )
    return _session_response(session, db)


@router.post("/{session_id}/chat")
def chat_interview(
    session_id: str,
    payload: ChatMessageRequest,
    current_user: CurrentUser,
    db: DbSession,
    session_factory: Annotated[Callable[[], Session], Depends(get_session_factory)],
) -> StreamingResponse:
    get_owned_interview_session(session_id, current_user.id, db)
    llm = get_llm_client(db, current_user.id)

    def event_stream():
        session_db = session_factory()
        try:
            result = run_chat_turn(
                session_id=session_id,
                user_id=current_user.id,
                content=payload.content,
                db=session_db,
                llm=llm,
            )
            for event in result.events:
                if event.get("type") == "tool_used":
                    continue
                yield _sse(event)
            state = _session_response(result.session, session_db)
            yield _sse({"type": "session_state", "session": state.model_dump(mode="json")})
            yield _sse({"type": "done", "completed": result.completed})
        except ChatTurnError as exc:
            yield _sse({"type": "error", "message": str(exc)})
        finally:
            session_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{session_id}/messages", response_model=list[InterviewMessageResponse])
def get_interview_messages(
    session_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> list[dict[str, object]]:
    get_owned_interview_session(session_id, current_user.id, db)
    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "phase": message.phase,
            "turn_id": message.turn_id,
            "token_count": message.token_count,
            "created_at": message.created_at,
        }
        for message in list_session_messages(db, session_id)
    ]


@router.get("/{session_id}/events", response_model=list[AgentEventResponse])
def get_interview_events(
    session_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> list[dict[str, object]]:
    get_owned_interview_session(session_id, current_user.id, db)
    events = db.scalars(
        select(AgentEventLog)
        .where(
            AgentEventLog.user_id == current_user.id,
            AgentEventLog.session_id == session_id,
        )
        .order_by(AgentEventLog.created_at.asc(), AgentEventLog.id.asc())
    ).all()
    return [
        {
            "id": event.id,
            "event_type": event.event_type,
            "node_name": event.node_name,
            "detail_json": event.detail_json,
            "duration_ms": event.duration_ms,
            "token_count": event.token_count,
            "error": event.error,
            "created_at": event.created_at,
        }
        for event in events
    ]


@router.post("/{session_id}/finish", response_model=InterviewSessionResponse)
def finish_interview(
    session_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> InterviewSessionResponse:
    session = finish_interview_session(session_id, current_user.id, db)
    return _session_response(session, db)


def _session_response(session: InterviewSession, db: Session) -> InterviewSessionResponse:
    open_turn = current_open_turn(session)
    return InterviewSessionResponse(
        id=session.id,
        job_id=session.job_id,
        job_title=session.job.title,
        company=session.job.company,
        resume_version_id=session.resume_version_id,
        resume_title=session.resume_version.title if session.resume_version else None,
        job_evaluation_id=session.job_evaluation_id,
        status=session.status,
        retrieval_mode=session.retrieval_mode,
        scoring_mode=session.scoring_mode,
        max_questions=session.max_questions,
        main_questions_answered=session.main_questions_answered,
        current_turn=_turn_response(open_turn) if open_turn else None,
        turns=[_turn_response(turn) for turn in session.turns],
        report=_load(session.report_json, None),
        checkpoint={
            "mode": interview_graph_checkpoint_mode(db),
            "status": session.status,
            "resume_session_id": session.id,
            "current_turn_id": open_turn.id if open_turn else None,
            "answered_turn_count": _answered_count(session),
        },
        created_at=session.created_at,
        updated_at=session.updated_at,
        completed_at=session.completed_at,
    )


def _turn_response(turn: InterviewTurn) -> InterviewTurnResponse:
    return InterviewTurnResponse(
        id=turn.id,
        turn_index=turn.turn_index,
        question_text=turn.question_text,
        question_type=turn.question_type,
        skill_tags=_load(turn.skill_tags_json, []),
        is_followup=turn.is_followup,
        followup_depth=turn.followup_depth,
        answer_text=turn.answer_text,
        score=turn.score,
        feedback=turn.feedback,
        evidence=_load(turn.evidence_json, []),
        status=turn.status,
        question_bank_item_external_id=(
            turn.question_bank_item.external_id if turn.question_bank_item else None
        ),
        created_at=turn.created_at,
        answered_at=turn.answered_at,
    )


def _history_item_response(session: InterviewSession) -> InterviewHistoryItemResponse:
    report = _load(session.report_json, {}) or {}
    return InterviewHistoryItemResponse(
        id=session.id,
        job_id=session.job_id,
        job_title=session.job.title,
        company=session.job.company,
        location=session.job.location,
        salary=session.job.salary,
        status=session.status,
        total_score=report.get("total_score"),
        question_count=_answered_count(session),
        main_questions_answered=session.main_questions_answered,
        created_at=session.created_at,
        completed_at=session.completed_at,
    )


def _answered_count(session: InterviewSession) -> int:
    return sum(
        1
        for turn in session.turns
        if turn.status == "answered" and turn.question_type not in {"opening", "closing"}
    )


def _delete_sessions(sessions: list[InterviewSession], db: Session) -> int:
    if not sessions:
        return 0
    for session in sessions:
        db.delete(session)
    db.commit()
    return len(sessions)


def _load(value: str | None, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _sse(data: dict[str, object]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
