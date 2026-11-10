"""검색 디버그용 엔드포인트: LLM 답변 없이 어떤 조문이 검색되는지 확인한다."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.lang import DEFAULT_LANG, Lang, today_kr
from app.retrieval.pipeline import retrieve
from app.retrieval.rewrite import resolve_as_of, rewrite_query

router = APIRouter(prefix="/search", tags=["debug"])


@router.get("")
async def search(
    q: str = Query(..., min_length=1),
    lang: Lang | None = None,
    as_of: date | None = None,
    rewrite: bool = True,
    session: AsyncSession = Depends(get_session),
):
    lang = lang or DEFAULT_LANG
    if rewrite:
        rq = await rewrite_query(q, lang, [])
        queries, domains, question = rq.queries_ko or [q], None, rq.standalone_question
        day = resolve_as_of(rq, as_of)
    else:
        queries, domains, question, day = [q], None, q, as_of or today_kr()
    items = await retrieve(
        session, queries, question, day, domains, include_samples=get_settings().include_samples
    )
    return {
        "queries_ko": queries,
        "domains": domains,
        "as_of": day,
        "results": [
            {"provision_id": i.provision_id, "path": i.path, "score": round(i.score, 4), "source": i.source}
            for i in items
        ],
    }
