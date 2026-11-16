"""US-01·07: 벌칙 추가 검색에도 조문·법령의 기준일과 샘플 제외 규칙을 적용한다."""
import asyncio
from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.retrieval import pipeline

DAY = date(2026, 11, 10)
BEFORE = date(2000, 1, 1)
FUTURE = date(2099, 1, 1)


@pytest.mark.db
@pytest.mark.parametrize("p_from,p_to,d_from,d_to,sample,include,expected", [
    (BEFORE, None, BEFORE, None, False, False, True),
    (DAY, None, BEFORE, None, False, False, True),
    (FUTURE, None, BEFORE, None, False, False, False),
    (BEFORE, DAY, BEFORE, None, False, False, False),
    (BEFORE, None, FUTURE, None, False, False, False),
    (BEFORE, None, BEFORE, DAY, False, False, False),
    (BEFORE, None, BEFORE, None, True, False, False),
    (BEFORE, None, BEFORE, None, True, True, True),
], ids=["valid", "effective-today", "future-article", "expired-article", "future-law", "expired-law",
        "sample-hidden", "sample-explicitly-enabled"])
def test_added_sanction_respects_reference_date_and_sample_scope(
    monkeypatch, p_from, p_to, d_from, d_to, sample, include, expected,
):
    prefix = "__sanction_test_" + uuid4().hex
    duty, penalty = prefix + "_duty", prefix + "_penalty"
    duty_id, sanction_id = duty + ":J1", penalty + ":J2"
    monkeypatch.setattr(pipeline, "hybrid_search", AsyncMock(return_value=({duty_id: 1.0}, {})))
    monkeypatch.setattr(pipeline, "expand", AsyncMock(return_value={}))

    async def run():
        try:
            async with SessionLocal() as session:
                await session.execute(text("""
                    INSERT INTO legal_documents (id, doc_type, title_ko, effective_from, effective_to, is_sample)
                    VALUES (:id, 'law', '검토용 가상 법령', :starts, :ends, :sample)
                """), [
                    {"id": duty, "starts": BEFORE, "ends": None, "sample": False},
                    {"id": penalty, "starts": d_from, "ends": d_to, "sample": sample},
                ])
                await session.execute(text("""
                    INSERT INTO provisions
                        (id, document_id, jo_id, level, number, path, ordinal, full_text_ko, effective_from, effective_to)
                    VALUES (:id, :doc, :id, 'jo', :num, :path, 1, '가상 조문', :starts, :ends)
                """), [
                    {"id": duty_id, "doc": duty, "num": "1", "path": "제1조", "starts": BEFORE, "ends": None},
                    {"id": sanction_id, "doc": penalty, "num": "2", "path": "벌칙 제2조",
                     "starts": p_from, "ends": p_to},
                ])
                await session.execute(text("""
                    INSERT INTO provision_edges (src_id, dst_id, rel)
                    VALUES (:src, :dst, 'REFERENCES')
                """), {"src": sanction_id, "dst": duty_id})
                results = await pipeline.retrieve(session, ["가상 의무"], "가상 의무", DAY, None,
                                                  include_samples=include)
                assert (sanction_id in {r.provision_id for r in results}) is expected
                await session.rollback()  # 검증용 가상 법령은 DB에 남기지 않는다
        finally:
            await engine.dispose()

    asyncio.run(run())
