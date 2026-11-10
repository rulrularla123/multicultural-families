"""미해결 질문(open_questions)과 API 사용량 요약."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.chat import OpenQuestionOut, UsageSummary, UsageTotals

router = APIRouter(prefix="/questions", tags=["questions"])
usage_router = APIRouter(prefix="/usage", tags=["usage"])

_COLUMNS = "id, created_at, session_id, analysis_id, source, question, resolved, resolved_at"


@router.get("", response_model=list[OpenQuestionOut])
async def list_questions(
    session_id: str | None = None,
    analysis_id: UUID | None = None,
    resolved: bool | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """세션·분석별 후속 질문 목록 (최신순). 조건을 주지 않으면 전체."""
    rows = (await session.execute(
        text(
            f"SELECT {_COLUMNS} FROM open_questions "
            "WHERE (CAST(:sid AS text) IS NULL OR session_id = :sid) "
            "AND (CAST(:aid AS uuid) IS NULL OR analysis_id = :aid) "
            "AND (CAST(:resolved AS boolean) IS NULL OR resolved = :resolved) "
            "ORDER BY created_at DESC, id DESC LIMIT :limit"
        ),
        {"sid": session_id, "aid": analysis_id, "resolved": resolved, "limit": limit},
    )).mappings().all()
    return [dict(r) for r in rows]


@router.post("/{question_id}/resolve", response_model=OpenQuestionOut)
async def resolve_question(question_id: int, session: AsyncSession = Depends(get_session)):
    row = (await session.execute(
        text(
            "UPDATE open_questions SET resolved = true, resolved_at = coalesce(resolved_at, now()) "
            f"WHERE id = :id RETURNING {_COLUMNS}"
        ),
        {"id": question_id},
    )).mappings().first()
    if row is None:
        raise HTTPException(404, "question_not_found")
    await session.commit()
    return dict(row)


@usage_router.get("/summary", response_model=UsageSummary)
async def usage_summary(days: int = Query(7, ge=1, le=90), session: AsyncSession = Depends(get_session)):
    """최근 N일(기본 7일) 종류별 토큰·비용 합계. 비용은 app.llm.PRICES_PER_1M 기준 추정치."""
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (await session.execute(
        text(
            "SELECT kind, count(*) AS requests, coalesce(sum(input_tokens), 0) AS input_tokens, "
            "coalesce(sum(output_tokens), 0) AS output_tokens, coalesce(sum(cost_usd), 0) AS cost_usd "
            "FROM usage_log WHERE created_at >= :since GROUP BY kind ORDER BY kind"
        ),
        {"since": since},
    )).mappings().all()
    by_kind = [
        UsageTotals(kind=r["kind"], requests=r["requests"], input_tokens=r["input_tokens"],
                    output_tokens=r["output_tokens"], cost_usd=round(float(r["cost_usd"]), 6))
        for r in rows
    ]
    total = UsageTotals(
        kind="all",
        requests=sum(k.requests for k in by_kind),
        input_tokens=sum(k.input_tokens for k in by_kind),
        output_tokens=sum(k.output_tokens for k in by_kind),
        cost_usd=round(sum(k.cost_usd for k in by_kind), 6),
    )
    return UsageSummary(since=since, days=days, by_kind=by_kind, total=total)
