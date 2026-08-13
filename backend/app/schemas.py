from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime


class ProfileRequest(BaseModel):
    target_role: str | None = Field(default=None, max_length=120)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    cities: str | None = Field(default=None, max_length=255)
    work_type: Literal["internship", "full_time"] | None = None
    deal_breakers: str | None = None


class ProfileResponse(ProfileRequest):
    id: str
    user_id: str


class ModelProviderRequest(BaseModel):
    provider: Literal["openai", "tongyi", "deepseek", "claude"]
    api_key: str = Field(min_length=1, max_length=512)
    model_name: str = Field(min_length=1, max_length=120)
    base_url: HttpUrl | None = None
    timeout_seconds: int = Field(default=30, ge=3, le=120)
    network_mode: Literal["auto", "direct", "manual_proxy"] = "auto"
    proxy_url: HttpUrl | None = None


class ModelProviderResponse(BaseModel):
    id: str
    provider: str
    model_name: str
    base_url: str | None
    timeout_seconds: int
    network_mode: str
    proxy_url: str | None
    masked_api_key: str
    updated_at: datetime


class ConnectionTestResponse(BaseModel):
    ok: bool
    provider: str
    message: str
    error_type: str | None = None


class ResumeVersionResponse(BaseModel):
    id: str
    version_no: int
    title: str
    extracted_text: str
    created_at: datetime


class ResumeFileResponse(BaseModel):
    id: str
    original_filename: str
    file_ext: str
    file_size: int
    is_default: bool
    created_at: datetime
    versions: list[ResumeVersionResponse]


class CreateJobCollectionSessionRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=120)
    city: str | None = Field(default=None, max_length=80)
    work_type: Literal["internship", "full_time"] | None = None
    limit: int = Field(default=20, ge=1, le=50)


class JobResponse(BaseModel):
    id: str
    title: str
    company: str
    location: str | None
    salary: str | None
    experience: str | None
    education: str | None
    tags: str | None
    job_url: str | None
    description: str | None
    is_in_pool: bool
    has_interviewed: bool = False
    created_at: datetime


class JobCollectionSessionResponse(BaseModel):
    id: str
    keyword: str
    city: str | None
    work_type: str | None
    limit: int
    status: str
    collection_token: str
    token_expires_at: datetime
    boss_search_url: str
    error_code: str | None
    error_message: str | None
    accepted_count: int = 0
    created_count: int = 0
    duplicated_count: int = 0
    filtered_count: int = 0
    jobs: list[JobResponse] = []


class JobCollectionSessionSummaryResponse(BaseModel):
    id: str
    keyword: str
    city: str | None
    work_type: str | None
    limit: int
    status: str
    boss_search_url: str
    error_code: str | None
    error_message: str | None
    accepted_count: int = 0
    created_count: int = 0
    duplicated_count: int = 0
    filtered_count: int = 0
    job_count: int = 0
    created_at: datetime
    updated_at: datetime


class JobCollectionSessionListResponse(BaseModel):
    items: list[JobCollectionSessionSummaryResponse]
    total: int
    page: int
    page_size: int


class DeleteJobCollectionSessionsRequest(BaseModel):
    session_ids: list[str] = Field(min_length=1, max_length=100)


class DeleteJobCollectionSessionsResponse(BaseModel):
    deleted_count: int


class DeleteJobPoolJobsRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1, max_length=100)


class DeleteJobPoolJobsResponse(BaseModel):
    removed_count: int


class CollectedJobItem(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    company: str = Field(min_length=1, max_length=180)
    location: str | None = Field(default=None, max_length=120)
    salary: str | None = Field(default=None, max_length=120)
    experience: str | None = Field(default=None, max_length=120)
    education: str | None = Field(default=None, max_length=120)
    tags: list[str] = []
    job_url: str | None = Field(default=None, max_length=500)
    description: str | None = None
    source_job_id: str | None = Field(default=None, max_length=120)


class SubmitCollectedJobsRequest(BaseModel):
    collection_token: str
    jobs: list[CollectedJobItem] = Field(default_factory=list)
    status: Literal["success", "partial_success", "failed"] = "success"
    error_code: str | None = Field(default=None, max_length=50)
    error_message: str | None = None


class SubmitCollectedJobsResponse(BaseModel):
    accepted: int
    created: int
    duplicated: int
    filtered: int = 0
    status: str


class CreateJobEvaluationRequest(BaseModel):
    resume_version_id: str | None = None
    model_provider_id: str | None = None


class JobEvaluationDimensionResponse(BaseModel):
    score: float
    weight: float
    data_status: Literal["sufficient", "insufficient_data"]
    explanation: str


class JobEvaluationResponse(BaseModel):
    id: str
    job_id: str
    resume_version_id: str
    resume_title: str | None = None
    model_provider_id: str | None = None
    framework_version: str
    prompt_version: str
    raw_weighted_score: float
    final_score: float
    recommendation: str
    one_sentence_reason: str
    language_gate_triggered: bool
    dealbreakers_hit: list[str]
    dimensions: dict[str, JobEvaluationDimensionResponse]
    highlights: list[str]
    risks_and_gaps: list[str]
    jd_requirements: dict[str, Any] = Field(default_factory=dict)
    salary_benchmark: dict[str, Any]
    evidence: list[str]
    resume_focus_suggestions: list[str]
    honest_gap_statements: list[str]
    created_at: datetime


class CreateInterviewSessionRequest(BaseModel):
    job_id: str
    resume_version_id: str | None = None
    max_questions: int = Field(default=5, ge=1, le=8)


class SubmitInterviewAnswerRequest(BaseModel):
    answer_text: str = Field(min_length=1, max_length=8000)


class InterviewTurnResponse(BaseModel):
    id: str
    turn_index: int
    question_text: str
    question_type: str
    skill_tags: list[str]
    is_followup: bool
    followup_depth: int
    answer_text: str | None
    score: float | None
    feedback: str | None
    evidence: list[str]
    status: str
    question_bank_item_external_id: str | None = None
    created_at: datetime
    answered_at: datetime | None = None


class InterviewSessionResponse(BaseModel):
    id: str
    job_id: str
    job_title: str
    company: str
    resume_version_id: str
    resume_title: str | None = None
    job_evaluation_id: str | None = None
    status: str
    retrieval_mode: str
    scoring_mode: str
    max_questions: int
    main_questions_answered: int
    current_turn: InterviewTurnResponse | None = None
    turns: list[InterviewTurnResponse]
    report: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class InterviewHistoryItemResponse(BaseModel):
    id: str
    job_id: str
    job_title: str
    company: str
    location: str | None = None
    salary: str | None = None
    status: str
    total_score: float | None = None
    question_count: int = 0
    main_questions_answered: int
    created_at: datetime
    completed_at: datetime | None = None


class DeleteInterviewSessionsRequest(BaseModel):
    session_ids: list[str] = Field(min_length=1, max_length=100)


class DeleteInterviewSessionsResponse(BaseModel):
    deleted_count: int
