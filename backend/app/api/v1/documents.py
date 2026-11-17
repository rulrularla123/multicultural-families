"""서류 분석 API. 모든 요청에 브라우저 익명 ID(X-Client-Id)가 필요하다.

POST   /api/v1/documents                 마스킹한 추출 텍스트 → 서버 재마스킹 → 서류 파악·개인화 질문 (status=questions)
GET    /api/v1/documents                 내 분석 건 목록
GET    /api/v1/documents/{id}            상태·단계·결과 (화면이 폴링)
POST   /api/v1/documents/{id}/answers    답변 제출 → 백그라운드 분석 (status=analyzing). 분석 실패 건 재시도
POST   /api/v1/documents/{id}/checklist  다음 행동 체크 (review ↔ done)
POST   /api/v1/documents/{id}/cancel     취소 (진행 중 → canceled)
DELETE /api/v1/documents/{id}            삭제
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.lang import Lang
from app.documents.extract import DOCX, MAX_BYTES, MAX_CHARS, MESSAGES, MIN_TEXT_CHARS, PDF
from app.services import documents as svc

router = APIRouter(prefix="/documents", tags=["documents"])

def client_id(x_client_id: Annotated[str | None, Header()] = None) -> str:
    cid = (x_client_id or "").strip()
    if not 8 <= len(cid) <= 64:
        raise HTTPException(400, "X-Client-Id header is required.")
    return cid


class Answer(BaseModel):
    question_id: str
    option_id: str | None = None
    text: str | None = Field(default=None, max_length=500)


class AnswersIn(BaseModel):
    answers: list[Answer] = Field(default_factory=list)


class ChecklistIn(BaseModel):
    index: int
    done: bool


def _errors(e: Exception):
    if isinstance(e, svc.AnalysisNotFound):
        return HTTPException(404, str(e))
    if isinstance(e, svc.AnalysisStateError):
        return HTTPException(409, str(e))
    if isinstance(e, svc.AnalysisLLMError):
        return HTTPException(502, str(e))
    return HTTPException(422, str(e))


class DocumentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=MAX_CHARS)
    format: str = Field(max_length=10)
    file_size: int = Field(ge=1, strict=True)
    page_count: int = Field(ge=1, le=2_147_483_647, strict=True)
    lang: Lang = "vi"


@router.post("", status_code=201)
async def upload(request: Request, cid: str = Depends(client_id), session: AsyncSession = Depends(get_session)):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(415, "Send extracted document text as JSON.")
    buffer = bytearray()
    async for chunk in request.stream():
        if len(buffer) + len(chunk) > 1024 * 1024:
            raise HTTPException(413, "Document text request is too large.")
        buffer.extend(chunk)
    try:
        body = DocumentIn.model_validate(json.loads(buffer))
        # Reject invalid Unicode before storing it, without echoing the input.
        body.text.encode("utf-8")
    except (ValidationError, ValueError, RecursionError):
        raise HTTPException(422, "Invalid document text request.") from None
    mime = {"pdf": PDF, "docx": DOCX}.get(body.format)
    if mime is None:
        raise HTTPException(415, MESSAGES["unsupported"][body.lang])
    if body.file_size > MAX_BYTES:
        raise HTTPException(413, MESSAGES["too_large"][body.lang])
    if "\0" in body.text or len(body.text.replace("\f", "").strip()) < MIN_TEXT_CHARS:
        raise HTTPException(422, MESSAGES["no_text"][body.lang])
    try:
        return await svc.create_analysis(
            session, cid, f"document.{body.format}", mime, body.file_size, body.page_count, body.text, body.lang
        )
    except svc.AnalysisError as e:
        raise _errors(e) from e


@router.get("")
async def mine(cid: str = Depends(client_id), session: AsyncSession = Depends(get_session)):
    return await svc.list_analyses(session, cid)


@router.get("/{analysis_id}")
async def get(analysis_id: str, cid: str = Depends(client_id), session: AsyncSession = Depends(get_session)):
    try:
        return await svc.get_analysis(session, cid, analysis_id)
    except svc.AnalysisError as e:
        raise _errors(e) from e


@router.post("/{analysis_id}/answers", status_code=202)
async def answers(
    analysis_id: str, body: AnswersIn, cid: str = Depends(client_id), session: AsyncSession = Depends(get_session)
):
    try:
        return await svc.submit_answers(session, cid, analysis_id, [a.model_dump() for a in body.answers])
    except svc.MissingAnswers as e:
        return JSONResponse(status_code=422, content={"detail": str(e), "missing_question_ids": e.missing})
    except svc.AnalysisError as e:
        raise _errors(e) from e


@router.post("/{analysis_id}/checklist")
async def checklist(
    analysis_id: str, body: ChecklistIn, cid: str = Depends(client_id), session: AsyncSession = Depends(get_session)
):
    try:
        return await svc.set_checklist(session, cid, analysis_id, body.index, body.done)
    except svc.AnalysisError as e:
        raise _errors(e) from e


@router.post("/{analysis_id}/cancel")
async def cancel(analysis_id: str, cid: str = Depends(client_id), session: AsyncSession = Depends(get_session)):
    try:
        return await svc.cancel_analysis(session, cid, analysis_id)
    except svc.AnalysisError as e:
        raise _errors(e) from e


@router.delete("/{analysis_id}", status_code=204)
async def delete(analysis_id: str, cid: str = Depends(client_id), session: AsyncSession = Depends(get_session)):
    try:
        await svc.delete_analysis(session, cid, analysis_id)
    except svc.AnalysisError as e:
        raise _errors(e) from e
