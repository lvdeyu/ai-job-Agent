from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    AgentEventLog,
    InterviewMessage,
    InterviewSession,
    InterviewTurn,
    QuestionBankItem,
    UserInterviewMemory,
)
from app.prompts.ask_question_v1 import ASK_QUESTION_V1
from app.prompts.context_assembler import (
    build_memory_prompt,
    build_system_prompt,
    messages_to_transcript,
)
from app.prompts.hr_system_v1 import HR_SYSTEM_V1
from app.prompts.judge_answer_v1 import JUDGE_ANSWER_V1
from app.services.interview import (
    CLOSING_QUESTION_TYPE,
    OPENING_QUESTION_TYPE,
    _move_job_application_status,
    build_interview_report,
    current_open_turn,
    evaluate_interview_answer,
    get_owned_interview_session,
    route_next_interview_turn,
    select_next_question,
)
from app.services.llm import LLMClient, LLMError
from app.services.tools import INTERVIEW_TOOL_SPECS, ToolExecutionContext, execute_tool

MAX_FOLLOWUP_DEPTH = 2
MAX_TOOL_ROUNDS = 2
_OPENING_STATIC = (
    "欢迎来到本场模拟面试，我是今天的面试官。"
    "先请你做一个 1 分钟左右的自我介绍，然后再开始正式提问。"
)


class ChatTurnError(RuntimeError):
    pass


@dataclass
class ChatTurnResult:
    session: InterviewSession
    assistant_message: str
    events: list[dict[str, Any]] = field(default_factory=list)
    completed: bool = False


def persist_message(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    turn_id: str | None = None,
    phase: str | None = None,
) -> InterviewMessage:
    message = InterviewMessage(
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content,
        turn_id=turn_id,
        phase=phase,
        token_count=max(0, len(content) // 4),
    )
    db.add(message)
    db.flush()
    return message


def _phase_for_turn(turn: InterviewTurn | None) -> str:
    if turn is None:
        return "probing"
    if turn.question_type == OPENING_QUESTION_TYPE:
        return "opening"
    if turn.question_type == CLOSING_QUESTION_TYPE:
        return "wrap_up"
    return "probing"


def _format_turn_prompt(turn: InterviewTurn) -> str:
    if turn.question_type in {OPENING_QUESTION_TYPE, CLOSING_QUESTION_TYPE}:
        return turn.question_text
    return f"{'追问：' if turn.is_followup else '下一题：'}{turn.question_text}"


def _complete_closing_turn(
    session: InterviewSession,
    turn: InterviewTurn,
    content: str,
    db: Session,
) -> tuple[InterviewSession, str]:
    turn.answer_text = content
    turn.score = None
    turn.feedback = "已记录用户反问。"
    turn.evidence_json = json.dumps([], ensure_ascii=False)
    turn.status = "answered"
    turn.answered_at = datetime.now(UTC)
    session.report_json = json.dumps(build_interview_report(session, db=db), ensure_ascii=False)
    session.status = "completed"
    session.completed_at = datetime.now(UTC)
    _move_job_application_status(session.job, "REVIEWED", only_from={"INTERVIEWING"})
    db.flush()
    _write_interview_memory(session, db)
    total = _report_total(session)
    message = f"感谢你的反问，面试到此结束。你的总分是 {total:.1f} 分，可以查看报告继续复盘。"
    return session, message


def list_session_messages(db: Session, session_id: str) -> list[InterviewMessage]:
    return list(
        db.scalars(
            select(InterviewMessage)
            .where(InterviewMessage.session_id == session_id)
            .order_by(InterviewMessage.created_at.asc(), InterviewMessage.id.asc())
        ).all()
    )


def run_chat_turn(
    *,
    session_id: str,
    user_id: str,
    content: str,
    db: Session,
    llm: LLMClient | None,
) -> ChatTurnResult:
    session = get_owned_interview_session(session_id, user_id, db)
    if session.status != "running":
        raise ChatTurnError("该模拟面试已经结束，不能继续对话。")

    messages = list_session_messages(db, session_id)
    open_turn = current_open_turn(session)
    if not messages and open_turn is not None and open_turn.question_type == OPENING_QUESTION_TYPE:
        persist_message(
            db,
            session_id=session.id,
            user_id=session.user_id,
            role="assistant",
            content=open_turn.question_text,
            turn_id=open_turn.id,
            phase="opening",
        )
        messages = list_session_messages(db, session_id)
    persist_message(db, session_id=session_id, user_id=user_id, role="user", content=content)

    if llm is None:
        result = _run_fallback_turn(session, content, db, messages)
    else:
        result = _run_llm_turn(session, content, db, llm, messages)

    db.commit()
    updated = get_owned_interview_session(session_id, user_id, db)
    result.session = updated
    return result


def _run_fallback_turn(
    session: InterviewSession,
    content: str,
    db: Session,
    messages: list[InterviewMessage],
) -> ChatTurnResult:
    events: list[dict[str, Any]] = []
    open_turn = current_open_turn(session)
    if not messages:
        if open_turn is not None and open_turn.question_type == OPENING_QUESTION_TYPE:
            persist_message(
                db,
                session_id=session.id,
                user_id=session.user_id,
                role="assistant",
                content=open_turn.question_text,
                turn_id=open_turn.id,
                phase="opening",
            )
        else:
            persist_message(
                db,
                session_id=session.id,
                user_id=session.user_id,
                role="assistant",
                content=_OPENING_STATIC,
                phase="opening",
            )
            events.append(
                {"type": "assistant_message", "message": _OPENING_STATIC, "phase": "opening"}
            )

    from app.services.interview import submit_interview_answer

    try:
        updated = submit_interview_answer(
            session_id=session.id,
            answer_text=content,
            user_id=session.user_id,
            db=db,
        )
    except Exception as exc:  # noqa: BLE001 - surface as chat error
        raise ChatTurnError(f"规则评分流程失败：{exc}") from exc

    if updated.status == "completed":
        total = _report_total(updated)
        closing = f"面试结束，你的总分为 {total:.1f} 分。你可以查看报告和逐题证据，继续复盘。"
        persist_message(
            db,
            session_id=session.id,
            user_id=session.user_id,
            role="assistant",
            content=closing,
            phase="report",
        )
        events.append({"type": "assistant_message", "message": closing, "phase": "report"})
        return ChatTurnResult(
            session=updated,
            assistant_message=closing,
            events=events,
            completed=True,
        )

    open_turn = current_open_turn(updated)
    if open_turn is None:
        raise ChatTurnError("面试已结束或当前没有待回答问题。")
    if open_turn.question_type == OPENING_QUESTION_TYPE:
        message = "谢谢你的自我介绍，我们开始正式提问。"
    else:
        message = _format_turn_prompt(open_turn)
    persist_message(
        db,
        session_id=session.id,
        user_id=session.user_id,
        role="assistant",
        content=message,
        turn_id=open_turn.id,
        phase="probing",
    )
    events.append({"type": "assistant_message", "message": message, "phase": "probing"})
    return ChatTurnResult(session=updated, assistant_message=message, events=events)


def _run_llm_turn(
    session: InterviewSession,
    content: str,
    db: Session,
    llm: LLMClient,
    messages: list[InterviewMessage],
) -> ChatTurnResult:
    events: list[dict[str, Any]] = []
    open_turn = current_open_turn(session)
    if not messages:
        if open_turn is not None and open_turn.question_type == OPENING_QUESTION_TYPE:
            persist_message(
                db,
                session_id=session.id,
                user_id=session.user_id,
                role="assistant",
                content=open_turn.question_text,
                turn_id=open_turn.id,
                phase="opening",
            )
        else:
            opening = _generate_opening(session, db, llm)
            persist_message(
                db,
                session_id=session.id,
                user_id=session.user_id,
                role="assistant",
                content=opening,
                phase="opening",
            )
            events.append({"type": "assistant_message", "message": opening, "phase": "opening"})

    from app.services.interview import submit_interview_answer

    if open_turn is not None and open_turn.question_type in {
        OPENING_QUESTION_TYPE,
        CLOSING_QUESTION_TYPE,
    }:
        if open_turn.question_type == CLOSING_QUESTION_TYPE:
            try:
                updated, closing_message = _complete_closing_turn(session, open_turn, content, db)
            except Exception as exc:  # noqa: BLE001 - surface as chat error
                raise ChatTurnError(f"收尾流程失败：{exc}") from exc
            persist_message(
                db,
                session_id=session.id,
                user_id=session.user_id,
                role="assistant",
                content=closing_message,
                phase="report",
            )
            events.append(
                {"type": "assistant_message", "message": closing_message, "phase": "report"}
            )
            return ChatTurnResult(
                session=updated,
                assistant_message=closing_message,
                events=events,
                completed=True,
            )
        try:
            updated = submit_interview_answer(
                session_id=session.id,
                answer_text=content,
                user_id=session.user_id,
                db=db,
            )
        except Exception as exc:  # noqa: BLE001 - surface as chat error
            raise ChatTurnError(f"规则评分流程失败：{exc}") from exc

        if updated.status == "completed":
            total = _report_total(updated)
            closing = f"面试结束，你的总分为 {total:.1f} 分。你可以查看报告和逐题证据，继续复盘。"
            persist_message(
                db,
                session_id=session.id,
                user_id=session.user_id,
                role="assistant",
                content=closing,
                phase="report",
            )
            events.append({"type": "assistant_message", "message": closing, "phase": "report"})
            return ChatTurnResult(
                session=updated,
                assistant_message=closing,
                events=events,
                completed=True,
            )

        next_turn = current_open_turn(updated)
        if next_turn is None:
            raise ChatTurnError("面试已结束或当前没有待回答问题。")
        message = "谢谢你的自我介绍，我们开始正式提问。"
        if next_turn.question_text not in message:
            message = f"{message}\n\n{_format_turn_prompt(next_turn)}"
        persist_message(
            db,
            session_id=session.id,
            user_id=session.user_id,
            role="assistant",
            content=message,
            turn_id=next_turn.id,
            phase=_phase_for_turn(next_turn),
        )
        events.append(
            {
                "type": "assistant_message",
                "message": message,
                "phase": _phase_for_turn(next_turn),
            }
        )
        return ChatTurnResult(session=updated, assistant_message=message, events=events)

    result: dict[str, Any] | None = None
    if open_turn is not None:
        result = evaluate_interview_answer(open_turn, content)
        open_turn.answer_text = content
        open_turn.score = result["score"]
        open_turn.feedback = result["feedback"]
        open_turn.evidence_json = json.dumps(result["evidence"], ensure_ascii=False)
        open_turn.status = "answered"
        open_turn.answered_at = datetime.now(UTC)
        if not open_turn.is_followup:
            session.main_questions_answered += 1
        db.flush()
        events.append(
            {
                "type": "score",
                "turn_id": open_turn.id,
                "score": result["score"],
                "feedback": result["feedback"],
            }
        )
        judge = _llm_judge(open_turn, content, llm)
        if judge is not None:
            if judge.get("feedback"):
                open_turn.feedback = str(judge["feedback"])
            explanation = str(judge.get("score_explanation") or "")
            if explanation:
                evidence = list(result["evidence"])
                evidence.append(f"面试官点评：{explanation}")
                open_turn.evidence_json = json.dumps(evidence, ensure_ascii=False)
                events.append({"type": "judge", "explanation": explanation})

    try:
        decision = _llm_decide(session, db, llm, content, events)
    except LLMError:
        decision = _fallback_decision(session, open_turn, result)
        events.append({"type": "llm_error", "message": "LLM 决策失败，已降级为规则决策。"})
    action = str(decision.get("action") or "converse")
    message = str(decision.get("message") or "好的，我们继续。")
    _write_event_log(
        db,
        session,
        event_type="llm_decision",
        node_name="llm_decide",
        detail={"action": action, "reason": decision.get("reason", "")},
    )

    completed = False
    new_turn: InterviewTurn | None = None
    if action == "close":
        if open_turn is None:
            raise ChatTurnError("面试已结束或当前没有待回答问题。")
        new_turn = route_next_interview_turn(session, open_turn, db)
        if new_turn is not None:
            db.add(new_turn)
            db.flush()
        message = _format_turn_prompt(new_turn) if new_turn is not None else _closing_message(session, decision)
    elif action == "next":
        new_turn = _ask_next_question(session, db, decision)
        if new_turn is not None and new_turn.question_type == CLOSING_QUESTION_TYPE:
            message = _format_turn_prompt(new_turn)
        if new_turn is None and session.status == "completed":
            message = _closing_message(session, decision)
            completed = True
            _write_interview_memory(session, db)
    elif action == "followup":
        new_turn = _ask_followup(session, db, decision)

    turn_id = None
    if new_turn is not None:
        turn_id = new_turn.id
        if action not in {"close"} and new_turn.question_type not in {
            OPENING_QUESTION_TYPE,
            CLOSING_QUESTION_TYPE,
        } and new_turn.question_text not in message:
            prefix = "追问：" if new_turn.is_followup else "下一题："
            message = f"{message}\n\n{prefix}{new_turn.question_text}"

    persist_message(
        db,
        session_id=session.id,
        user_id=session.user_id,
        role="assistant",
        content=message,
        turn_id=turn_id,
        phase="report" if completed else _phase_for_turn(new_turn),
    )
    events.append(
        {
            "type": "assistant_message",
            "message": message,
            "phase": "report" if completed else _phase_for_turn(new_turn),
        }
    )
    return ChatTurnResult(
        session=session,
        assistant_message=message,
        events=events,
        completed=completed,
    )


def _fallback_decision(
    session: InterviewSession,
    open_turn: InterviewTurn | None,
    result: dict[str, Any] | None,
) -> dict[str, Any]:
    if session.main_questions_answered >= session.max_questions:
        return {
            "action": "close",
            "message": "主问题已经问完，进入收尾并生成报告。",
            "reason": "llm_failed_guard",
        }
    if (
        result is not None
        and open_turn is not None
        and not open_turn.is_followup
        and float(result.get("score") or 0) < 70
        and open_turn.followup_depth < MAX_FOLLOWUP_DEPTH
    ):
        followups = json.loads(open_turn.followup_suggestions_json or "[]")
        if followups:
            return {
                "action": "followup",
                "message": "我再追问一下刚才的内容。",
                "question_text": followups[0],
                "reason": "llm_failed_followup",
            }
    return {
        "action": "next",
        "message": "好的，我们继续下一题。",
        "reason": "llm_failed_next",
    }


def _llm_judge(
    turn: InterviewTurn,
    answer_text: str,
    llm: LLMClient,
) -> dict[str, Any] | None:
    rubric = json.loads(turn.scoring_rubric_json or "[]")
    messages = [
        {"role": "system", "content": JUDGE_ANSWER_V1},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": turn.question_text,
                    "reference_answer": turn.reference_answer_snapshot,
                    "rubric": rubric,
                    "answer": answer_text,
                },
                ensure_ascii=False,
            ),
        },
    ]
    try:
        return llm.chat_json(messages, max_tokens=400)
    except LLMError:
        return None


def _generate_opening(session: InterviewSession, db: Session, llm: LLMClient) -> str:
    system = HR_SYSTEM_V1 + "\n\n" + build_system_prompt(session)
    memory = build_memory_prompt(db, session)
    if memory:
        system += "\n\n" + memory
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "请作为面试官做开场白，并引导求职者做 1 分钟自我介绍。"},
    ]
    try:
        return llm.chat(messages, max_tokens=200, temperature=0.7).strip()
    except LLMError:
        return _OPENING_STATIC


def _llm_decide(
    session: InterviewSession,
    db: Session,
    llm: LLMClient,
    content: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    transcript = messages_to_transcript(list_session_messages(db, session.id))
    system = HR_SYSTEM_V1 + "\n\n" + build_system_prompt(session) + "\n\n" + ASK_QUESTION_V1
    memory = build_memory_prompt(db, session)
    if memory:
        system += "\n\n" + memory
    messages = [{"role": "system", "content": system}]
    messages.extend(transcript[-14:])
    messages.append({"role": "user", "content": f"求职者最新发言：\n{content}"})

    tool_context = ToolExecutionContext(db=db, session=session)
    for _ in range(MAX_TOOL_ROUNDS):
        _, calls = llm.chat_with_tools(messages, INTERVIEW_TOOL_SPECS, max_tokens=1200)
        if not calls:
            break
        for call in calls:
            tool_result = execute_tool(call.name, call.arguments, tool_context)
            events.append(
                {
                    "type": "tool_used",
                    "tool": call.name,
                    "summary": _tool_summary(tool_result),
                }
            )
            _write_event_log(
                db,
                session,
                event_type="tool_call",
                node_name=call.name,
                detail={"arguments": call.arguments, "result": tool_result},
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"工具 {call.name} 返回："
                        f"{json.dumps(tool_result, ensure_ascii=False)[:1500]}"
                    ),
                }
            )

    final_messages = messages + [
        {
            "role": "user",
            "content": (
                "请基于以上信息和规则，输出最终决策 JSON（只输出 JSON，不要解释）。"
                "action 只能是 converse/next/followup/close 之一。"
            ),
        }
    ]
    decision = llm.chat_json(final_messages, max_tokens=800)
    action = str(decision.get("action") or "converse")
    if action not in {"converse", "next", "followup", "close"}:
        action = "converse"
    decision["action"] = action
    return decision


def _ask_next_question(
    session: InterviewSession,
    db: Session,
    decision: dict[str, Any],
) -> InterviewTurn | None:
    if session.main_questions_answered >= session.max_questions:
        closing_turn = next(
            (turn for turn in session.turns if turn.question_type == CLOSING_QUESTION_TYPE),
            None,
        )
        if closing_turn is not None and closing_turn.status == "asked":
            return None
        parent = next((turn for turn in reversed(session.turns) if turn.status == "answered"), None)
        if parent is None:
            return None
        next_index = max((turn.turn_index for turn in session.turns), default=0) + 1
        turn = InterviewTurn(
            session_id=session.id,
            user_id=session.user_id,
            question_bank_item_id=None,
            parent_turn_id=parent.id,
            turn_index=next_index,
            question_text="感谢你的回答，最后想请你反问我一个问题，你最想了解什么？",
            question_type=CLOSING_QUESTION_TYPE,
            skill_tags_json="[]",
            reference_answer_snapshot="",
            scoring_rubric_json="[]",
            followup_suggestions_json="[]",
            is_followup=False,
            followup_depth=0,
            status="asked",
        )
        db.add(turn)
        db.flush()
        return turn
    turn = _build_next_turn(session, db, decision)
    db.add(turn)
    db.flush()
    return turn


def _build_next_turn(
    session: InterviewSession,
    db: Session,
    decision: dict[str, Any],
) -> InterviewTurn:
    item_id = decision.get("question_bank_item_id")
    item = None
    if item_id:
        item = db.get(QuestionBankItem, item_id)
    if item is None:
        asked_ids = {
            turn.question_bank_item_id
            for turn in session.turns
            if turn.question_bank_item_id and not turn.is_followup
        }
        item = select_next_question(
            db=db,
            job=session.job,
            resume_version=session.resume_version,
            evaluation=session.job_evaluation,
            asked_question_bank_item_ids=asked_ids,
        )
    next_index = max((turn.turn_index for turn in session.turns), default=0) + 1
    if item is not None:
        question_text = str(decision.get("question_text") or item.question_text)
        return InterviewTurn(
            session_id=session.id,
            user_id=session.user_id,
            question_bank_item_id=item.id,
            turn_index=next_index,
            question_text=question_text,
            question_type=item.question_type,
            skill_tags_json=item.skill_tags_json,
            reference_answer_snapshot=item.reference_answer,
            scoring_rubric_json=item.scoring_rubric_json,
            followup_suggestions_json=item.followup_suggestions_json,
            is_followup=False,
            followup_depth=0,
            status="asked",
        )
    question_text = str(decision.get("question_text") or "")
    if not question_text:
        question_text = (
            f"结合 JD 对「岗位核心技能」的要求和你的项目经历，"
            f"说明你会如何在 {session.job.title or '该岗位'} 相关项目中落地，并给出具体实现步骤。"
        )
    return InterviewTurn(
        session_id=session.id,
        user_id=session.user_id,
        question_bank_item_id=None,
        turn_index=next_index,
        question_text=question_text,
        question_type="skill",
        skill_tags_json=json.dumps(["岗位核心技能"], ensure_ascii=False),
        reference_answer_snapshot="",
        scoring_rubric_json="[]",
        followup_suggestions_json="[]",
        is_followup=False,
        followup_depth=0,
        status="asked",
    )


def _ask_followup(
    session: InterviewSession,
    db: Session,
    decision: dict[str, Any],
) -> InterviewTurn | None:
    answered = [turn for turn in session.turns if turn.status == "answered"]
    if not answered:
        return _ask_next_question(session, db, decision)
    parent = answered[-1]
    if parent.is_followup:
        return _ask_next_question(session, db, decision)
    if parent.followup_depth >= MAX_FOLLOWUP_DEPTH:
        return _ask_next_question(session, db, decision)
    followups = json.loads(parent.followup_suggestions_json or "[]")
    question_text = str(decision.get("question_text") or "")
    if not question_text and followups:
        question_text = followups[0]
    if not question_text:
        return _ask_next_question(session, db, decision)
    next_index = max((turn.turn_index for turn in session.turns), default=0) + 1
    turn = InterviewTurn(
        session_id=session.id,
        user_id=session.user_id,
        question_bank_item_id=parent.question_bank_item_id,
        parent_turn_id=parent.id,
        turn_index=next_index,
        question_text=question_text,
        question_type="followup",
        skill_tags_json=parent.skill_tags_json,
        reference_answer_snapshot=parent.reference_answer_snapshot,
        scoring_rubric_json=parent.scoring_rubric_json,
        followup_suggestions_json="[]",
        is_followup=True,
        followup_depth=parent.followup_depth + 1,
        status="asked",
    )
    db.add(turn)
    db.flush()
    return turn


def _closing_message(session: InterviewSession, decision: dict[str, Any]) -> str:
    total = float(_report_total(session))
    return (
        str(decision.get("message") or "")
        or f"面试结束，你的总分为 {total:.1f} 分。报告已生成，可以去面试历史里查看。"
    )


def _close_interview(session: InterviewSession, db: Session, decision: dict[str, Any]) -> str:
    session.main_questions_answered = sum(
        1 for turn in session.turns if turn.status == "answered" and not turn.is_followup
    )
    report = build_interview_report(session, db=db)
    session.report_json = json.dumps(report, ensure_ascii=False)
    session.status = "completed"
    session.completed_at = datetime.now(UTC)
    _move_job_application_status(session.job, "REVIEWED", only_from={"INTERVIEWING"})
    db.flush()
    return _closing_message(session, decision)


def _write_interview_memory(session: InterviewSession, db: Session) -> None:
    if not session.report_json:
        return
    try:
        report = json.loads(session.report_json)
    except json.JSONDecodeError:
        return
    dimensions = report.get("skill_dimensions") or []
    if not dimensions:
        return
    db.execute(
        delete(UserInterviewMemory).where(
            UserInterviewMemory.user_id == session.user_id,
            UserInterviewMemory.job_id == session.job_id,
        )
    )
    for dimension in dimensions:
        skill = str(dimension.get("skill") or "")
        score = float(dimension.get("score") or 0)
        weak = "表现稳定，可继续巩固项目证据" if score >= 60 else "需补强项目证据与边界说明"
        db.add(
            UserInterviewMemory(
                user_id=session.user_id,
                job_id=session.job_id,
                skill=skill,
                strength_score=score,
                weak_points=json.dumps([weak], ensure_ascii=False),
                last_session_id=session.id,
            )
        )
    db.flush()


def _write_event_log(
    db: Session,
    session: InterviewSession,
    *,
    event_type: str,
    node_name: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        AgentEventLog(
            user_id=session.user_id,
            session_id=session.id,
            event_type=event_type,
            node_name=node_name,
            detail_json=json.dumps(detail or {}, ensure_ascii=False)[:4000],
        )
    )


def _tool_summary(result: dict[str, Any]) -> str:
    if result.get("ok") is False:
        return f"失败：{result.get('error', '')}"
    count = result.get("count")
    if count is not None:
        return f"返回 {count} 条结果"
    return "ok"


def _report_total(session: InterviewSession) -> float:
    if not session.report_json:
        return 0.0
    try:
        return float(json.loads(session.report_json).get("total_score") or 0)
    except (json.JSONDecodeError, TypeError):
        return 0.0
