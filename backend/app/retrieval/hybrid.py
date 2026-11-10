"""하이브리드 검색: BM25(메모리 색인) + 벡터(pgvector) → 조 단위 RRF 결합."""

import asyncio
import logging
from collections import defaultdict
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal, vector_literal
from app.llm import embed_texts
from app.retrieval.bm25 import get_index

log = logging.getLogger(__name__)

# 조문과 문서가 모두 기준일에 유효해야 한다
VALID = """
  (p.effective_from IS NULL OR p.effective_from <= :as_of)
  AND (p.effective_to IS NULL OR p.effective_to > :as_of)
  AND (d.effective_from IS NULL OR d.effective_from <= :as_of)
  AND (d.effective_to IS NULL OR d.effective_to > :as_of)
  AND d.status = 'in_force'
  AND (CAST(:domains AS text[]) IS NULL OR c.domains && CAST(:domains AS text[]) OR cardinality(c.domains) = 0)
  AND (:include_samples OR NOT d.is_sample)
"""

VECTOR_SQL = text(
    f"""
    SELECT c.jo_id, c.provision_id, 1 - (c.embedding <=> CAST(:vec AS vector)) AS score
    FROM chunks c
    JOIN provisions p ON p.id = c.provision_id
    JOIN legal_documents d ON d.id = c.document_id
    WHERE c.embedding IS NOT NULL AND {VALID}
    ORDER BY c.embedding <=> CAST(:vec AS vector)
    LIMIT :k
    """
)


def rrf_merge(ranked_lists: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion. 같은 조가 여러 청크로 나오면 가장 높은 순위만 센다."""
    scores: dict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        seen: set[str] = set()
        rank = 0
        for item in ranked:
            if item in seen:
                continue
            seen.add(item)
            rank += 1
            scores[item] += 1.0 / (k + rank)
    return dict(scores)


async def hybrid_search(
    session: AsyncSession,
    queries_ko: list[str],
    original: str,
    as_of: date,
    domains: list[str] | None,
    k: int,
    include_samples: bool = False,
) -> tuple[dict[str, float], dict[str, set[str]]]:
    """(조별 RRF 점수, 조별로 실제 매칭된 항·청크의 조문 ID)"""
    params = {
        "as_of": as_of,
        "domains": [d for d in (domains or []) if d != "other"] or None,
        "k": k,
        "include_samples": include_samples,
    }
    ranked: list[list[str]] = []
    matched: dict[str, set[str]] = defaultdict(set)

    # BM25는 질의별로 따로 순위를 매겨 RRF에 넣는다 (원문 질문도 베트남어 요약 청크와 맞춰 본다)
    index = await get_index(session)
    for q in dict.fromkeys([*queries_ko, original]):
        hits = index.search(q, as_of, k, include_samples=include_samples)
        if hits:
            ranked.append([jo for jo, _, _ in hits])
            for jo, pid, _ in hits[:20]:
                matched[jo].add(pid)

    # 한국어 질의 + 원문(베트남어) 질문을 모두 임베딩: 베트남어 원문은 베트남어 요약 청크와 잘 맞는다
    texts = list(dict.fromkeys([*queries_ko, original]))
    try:
        vectors = await embed_texts(texts)
    except Exception:  # API 키 미설정·장애 시 BM25만으로 계속
        log.warning("질의 임베딩 실패, BM25 결과만 사용", exc_info=True)
        return rrf_merge(ranked), matched

    async def vector_search(vec: list[float]):
        # 동시에 여러 쿼리를 돌리기 위해 세션을 따로 연다 (AsyncSession은 동시 사용 불가)
        async with SessionLocal() as s:
            return (await s.execute(VECTOR_SQL, {**params, "vec": vector_literal(vec)})).all()

    for rows in await asyncio.gather(*(vector_search(v) for v in vectors)):
        ranked.append([r.jo_id for r in rows])
        for r in rows[:20]:
            matched[r.jo_id].add(r.provision_id)
    return rrf_merge(ranked), matched
