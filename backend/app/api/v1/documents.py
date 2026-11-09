"""서류 분석 API. 모든 요청에 브라우저 익명 ID(X-Client-Id)가 필요하다.

POST   /api/v1/documents                 파일 업로드 → 추출·마스킹 → 서류 파악·개인화 질문 (status=questions)
GET    /api/v1/documents                 내 분석 건 목록
GET    /api/v1/documents/samples         샘플 서류 목록
POST   /api/v1/documents/samples/{id}    샘플로 분석 건 만들기
GET    /api/v1/documents/{id}            상태·단계·결과 (화면이 폴링)
POST   /api/v1/documents/{id}/answers    답변 제출 → 백그라운드 분석 (status=analyzing). 분석 실패 건 재시도
POST   /api/v1/documents/{id}/checklist  다음 행동 체크 (review ↔ done)
POST   /api/v1/documents/{id}/cancel     취소 (진행 중 → canceled)
DELETE /api/v1/documents/{id}            삭제
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.lang import Lang
from app.documents.extract import DOCX, UnsupportedDocument
from app.services import documents as svc

router = APIRouter(prefix="/documents", tags=["documents"])

DEMO_DIR = Path(__file__).resolve().parents[3] / "data" / "demo"
# 시연용 가상 문서 (실제 서류·개인정보 아님)
SAMPLES = {
    "extension-guide": {
        "file": "sample-extension-guide.docx",
        "title": {"vi": "Mẫu · Hướng dẫn gia hạn lưu trú (F-6-1)", "ko": "샘플 · 체류기간 연장 안내문 (F-6-1)"},
    },
    "address-report": {
        "file": "sample-address-change-notice.docx",
        "title": {"vi": "Mẫu · Thông báo khai báo thay đổi nơi cư trú", "ko": "샘플 · 체류지 변경신고 안내"},
    },
}


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
    if isinstance(e, UnsupportedDocument):
        return HTTPException(e.status, str(e))
    if isinstance(e, svc.AnalysisNotFound):
        return HTTPException(404, str(e))
    if isinstance(e, svc.AnalysisStateError):
        return HTTPException(409, str(e))
    if isinstance(e, svc.AnalysisLLMError):
        return HTTPException(502, str(e))
    return HTTPException(422, str(e))


@router.post("", status_code=201)
async def upload(
    file: UploadFile = File(...),
    lang: Lang = Form("vi"),
    cid: str = Depends(client_id),
    session: AsyncSession = Depends(get_session),
):
    data = await file.read()
    try:
        return await svc.create_analysis(session, cid, file.filename or "document", file.content_type, data, lang)
    except (UnsupportedDocument, svc.AnalysisError) as e:
        raise _errors(e) from e


@router.get("/samples")
async def samples():
    return [{"id": k, "title": v["title"], "filename": v["file"]} for k, v in SAMPLES.items()]


@router.post("/samples/{sample_id}", status_code=201)
async def analyze_sample(
    sample_id: str, lang: Lang = Form("vi"), cid: str = Depends(client_id), session: AsyncSession = Depends(get_session)
):
    sample = SAMPLES.get(sample_id)
    if sample is None:
        raise HTTPException(404, "Sample not found.")
    data = (DEMO_DIR / sample["file"]).read_bytes()
    try:
        return await svc.create_analysis(session, cid, sample["file"], DOCX, data, lang)
    except (UnsupportedDocument, svc.AnalysisError) as e:
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
