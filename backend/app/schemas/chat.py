from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.lang import Lang


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    lang: Lang | None = Field(default=None, description="응답 언어 vi(기본)·ko. 질문은 어떤 언어든 가능")
    as_of: date | None = Field(default=None, description="이 날짜 기준 유효한 법령으로 답변 (기본: 오늘)")
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    session_id: str | None = Field(
        default=None, max_length=100, description="앱이 만든 대화 세션 ID. 미해결 질문(open_questions) 추적에 쓴다"
    )
    analysis_id: UUID | None = Field(default=None, description="분석한 문서에 대한 후속 질문이면 그 분석 ID")
    client_id: str | None = Field(default=None, exclude=True, description="서버가 X-Client-Id 헤더로 채운다")


    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must contain non-whitespace characters")
        return value  # 공백·줄바꿈도 원래 1,000자 상한에 포함한다.


class CitationOut(BaseModel):
    index: int
    provision_id: str
    quote_ko: str
    quote_translation: str
    verified: bool
    verify_error: str | None


class SourceOut(BaseModel):
    provision_id: str
    document_id: str
    title: str
    path: str
    retrieved_by: str


class NumberCheckOut(BaseModel):
    text: str = Field(description="답변에 나온 숫자 표현 그대로, 예: '14 ngày', '100 triệu won'")
    values: list[float]
    unit: Literal["krw", "months", "days", "years"]
    status: Literal["verified", "not_found"]
    provision_id: str | None = Field(description="숫자가 확인된 조문 ID (분석 문서에서 찾았으면 'document:C3')")
    missing: list[float] = Field(default_factory=list, description="원문에서 찾지 못한 값")


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: float
    calls: int


class AnswerPayload(BaseModel):
    kind: Literal["answer", "smalltalk", "unclear", "no_results"] = Field(
        default="answer", description="answer 외에는 검색·근거 없이 안내만 한 응답 (화면에서 확신도 표시 안 함)")
    lang: Lang
    as_of: date
    answer: str
    citations: list[CitationOut]
    confidence: Literal["high", "medium", "low"]
    needs_expert: bool
    follow_up_questions: list[str]
    notice: str | None
    disclaimer: str
    sources: list[SourceOut]
    search_queries: list[str]
    number_checks: list[NumberCheckOut] = Field(default_factory=list)
    analysis_id: UUID | None = None
    usage: UsageOut | None = None


class OpenQuestionOut(BaseModel):
    id: int
    created_at: datetime
    session_id: str | None
    analysis_id: UUID | None
    source: Literal["chat", "analysis"]
    question: str
    resolved: bool
    resolved_at: datetime | None


class UsageTotals(BaseModel):
    kind: str
    requests: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class UsageSummary(BaseModel):
    since: datetime
    days: int
    by_kind: list[UsageTotals]
    total: UsageTotals
