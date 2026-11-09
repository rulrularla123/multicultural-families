"""메모리 BM25 색인.

Postgres ts_rank_cd는 문서 길이 보정이 없어서 개정 법률처럼 아주 긴 조문이 항상 상위에 올라온다.
코퍼스(수천~수만 청크)가 메모리에 충분히 들어가므로 표준 BM25(Okapi, k1=1.5, b=0.75)를 직접 계산한다.
청크 수·최대 ID가 바뀌면(재적재) 자동으로 다시 만든다.
"""

import asyncio
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ingest.nlp.tokenize import tokenize_ko

K1, B = 1.5, 0.75
_WORD = re.compile(r"[^\W_]+", re.UNICODE)

ROWS_SQL = text(
    """
    SELECT c.id, c.jo_id, c.provision_id, c.lang, c.tokens, c.content,
           greatest(p.effective_from, d.effective_from) AS eff_from,
           least(coalesce(p.effective_to, d.effective_to), coalesce(d.effective_to, p.effective_to)) AS eff_to,
           d.status, d.is_sample
    FROM chunks c
    JOIN provisions p ON p.id = c.provision_id
    JOIN legal_documents d ON d.id = c.document_id
    """
)
SIGNATURE_SQL = text("SELECT count(*), coalesce(max(id), 0) FROM chunks")


@dataclass
class _Doc:
    jo_id: str
    provision_id: str
    length: int
    eff_from: date | None
    eff_to: date | None
    status: str
    is_sample: bool


def _terms(lang: str, tokens: str | None, content: str) -> list[str]:
    if tokens:
        return tokens.split()
    return tokenize_ko(content)  # 요약 청크(베트남어·한국어)도 같은 토큰화


def query_terms(query: str) -> list[str]:
    """한글 2-gram + 베트남어·영문 어절"""
    return list(dict.fromkeys(tokenize_ko(query)))


class BM25Index:
    def __init__(self, rows):
        self.docs: list[_Doc] = []
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        total = 0
        for i, r in enumerate(rows):
            terms = _terms(r.lang, r.tokens, r.content)
            for term, tf in Counter(terms).items():
                self.postings[term].append((i, tf))
            self.docs.append(_Doc(r.jo_id, r.provision_id, len(terms), r.eff_from, r.eff_to, r.status, r.is_sample))
            total += len(terms)
        self.n = len(self.docs)
        self.avgdl = total / self.n if self.n else 1.0
        self.idf = {t: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}

    def _valid(self, d: _Doc, as_of: date, include_samples: bool) -> bool:
        if d.is_sample and not include_samples:
            return False
        if d.status != "in_force":
            return False
        if d.eff_from and d.eff_from > as_of:
            return False
        return not (d.eff_to and d.eff_to <= as_of)

    def search(self, query: str, as_of: date, k: int, include_samples: bool = False) -> list[tuple[str, str, float]]:
        """(조 ID, 청크의 조문 ID, 점수) 목록"""
        scores: dict[int, float] = defaultdict(float)
        for term in query_terms(query):
            idf = self.idf.get(term)
            if not idf:
                continue
            for i, tf in self.postings[term]:
                dl = self.docs[i].length
                scores[i] += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * dl / self.avgdl))
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        out: list[tuple[str, str, float]] = []
        for i, s in ranked:
            d = self.docs[i]
            if self._valid(d, as_of, include_samples):
                out.append((d.jo_id, d.provision_id, s))
                if len(out) >= k:
                    break
        return out


_index: BM25Index | None = None
_signature: tuple | None = None
_lock = asyncio.Lock()


async def get_index(session: AsyncSession) -> BM25Index:
    global _index, _signature
    sig = tuple((await session.execute(SIGNATURE_SQL)).one())
    if _index is not None and sig == _signature:
        return _index
    async with _lock:
        if _index is None or sig != _signature:
            rows = (await session.execute(ROWS_SQL)).all()
            _index = await asyncio.to_thread(BM25Index, rows)
            _signature = sig
    return _index
