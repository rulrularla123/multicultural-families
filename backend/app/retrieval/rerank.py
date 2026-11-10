"""리랭커. 기본은 'none'(검색 점수 순서 유지), 설정으로 크로스인코더를 켠다."""

import asyncio
from functools import lru_cache

from app.core.config import get_settings


class Reranker:
    async def score(self, query: str, docs: list[str]) -> list[float] | None:
        return None


class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder  # pip install -e ".[rerank]"

        self.model = CrossEncoder(model_name, max_length=1024)

    async def score(self, query: str, docs: list[str]) -> list[float]:
        pairs = [(query, d) for d in docs]
        scores = await asyncio.to_thread(self.model.predict, pairs)
        return [float(s) for s in scores]


@lru_cache
def get_reranker() -> Reranker:
    s = get_settings()
    if s.reranker == "cross-encoder":
        return CrossEncoderReranker(s.reranker_model)
    return Reranker()
