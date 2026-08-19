from app.prompts.ask_question_v1 import ASK_QUESTION_V1, ASK_QUESTION_V1_VERSION
from app.prompts.closing_v1 import CLOSING_V1, CLOSING_V1_VERSION
from app.prompts.hr_system_v1 import HR_SYSTEM_V1, HR_SYSTEM_V1_VERSION
from app.prompts.interview_plan_v1 import INTERVIEW_PLAN_V1, INTERVIEW_PLAN_V1_VERSION
from app.prompts.judge_answer_v1 import JUDGE_ANSWER_V1, JUDGE_ANSWER_V1_VERSION

PROMPT_VERSIONS = {
    "hr_system": HR_SYSTEM_V1_VERSION,
    "interview_plan": INTERVIEW_PLAN_V1_VERSION,
    "ask_question": ASK_QUESTION_V1_VERSION,
    "judge_answer": JUDGE_ANSWER_V1_VERSION,
    "closing": CLOSING_V1_VERSION,
}

__all__ = [
    "ASK_QUESTION_V1",
    "ASK_QUESTION_V1_VERSION",
    "CLOSING_V1",
    "CLOSING_V1_VERSION",
    "HR_SYSTEM_V1",
    "HR_SYSTEM_V1_VERSION",
    "INTERVIEW_PLAN_V1",
    "INTERVIEW_PLAN_V1_VERSION",
    "JUDGE_ANSWER_V1",
    "JUDGE_ANSWER_V1_VERSION",
    "PROMPT_VERSIONS",
]
