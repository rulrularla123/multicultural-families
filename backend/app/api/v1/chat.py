import json
import logging
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.chat import AnswerPayload, ChatRequest
from app.services.qa import AnalysisContext, answer_stream, load_analysis_context

router = APIRouter(prefix="/chat", tags=["chat"])
log = logging.getLogger(__name__)


async def _analysis(session: AsyncSession, req: ChatRequest, client_id: str | None) -> AnalysisContext | None:
    """문서 후속 질문이면 본인 분석을 먼저 불러온다. 없거나 남의 건이면 스트림 시작 전에 404."""
    req.client_id = (client_id or "").strip() or None
    if not req.analysis_id:
        return None
    if not req.client_id:
        raise HTTPException(400, "X-Client-Id header is required.")
    ctx = await load_analysis_context(session, req.analysis_id, req.client_id)
    if ctx is None:
        raise HTTPException(404, "analysis_not_found")
    return ctx


@router.post("", response_model=AnswerPayload)
async def chat(
    req: ChatRequest,
    x_client_id: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
):
    """단계 이벤트 없이 최종 답변만 JSON으로 돌려준다."""
    analysis = await _analysis(session, req, x_client_id)
    async with aclosing(answer_stream(session, req, analysis)) as events:
        async for ev in events:
            if ev["event"] == "answer":
                return ev["data"]
    raise RuntimeError("answer 이벤트가 생성되지 않았습니다")


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    x_client_id: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
):
    """SSE: event: stage (진행 단계) … delta … (reset) … event: answer (최종 답변) / event: error"""
    analysis = await _analysis(session, req, x_client_id)

    async def gen():
        try:
            async with aclosing(answer_stream(session, req, analysis)) as events:
                async for ev in events:
                    yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], ensure_ascii=False, default=str)}\n\n"
        except Exception:
            log.exception("chat stream 실패")
            yield 'event: error\ndata: {"message": "internal_error"}\n\n'

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
