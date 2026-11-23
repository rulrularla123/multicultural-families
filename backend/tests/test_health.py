"""US-07 적재된 DB의 /health 응답을 검증한다."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import SessionLocal, engine
from app.main import app
from app.models.law import Chunk, LegalDocument, Provision


@pytest.mark.db
def test_health_reports_ingested_counts():
    async def count_rows():
        async with SessionLocal() as session:
            return {
                "documents": await session.scalar(select(func.count(LegalDocument.id))),
                "provisions": await session.scalar(select(func.count(Provision.id))),
                "chunks": await session.scalar(select(func.count(Chunk.id))),
                "embedded": await session.scalar(select(func.count(Chunk.embedding))),
            }

    with TestClient(app) as client:
        try:
            response = client.get("/health")
            expected = client.portal.call(count_rows)
        finally:
            client.portal.call(engine.dispose)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    for key, count in expected.items():
        assert type(body[key]) is int
        assert body[key] == count
    assert body["documents"] > 0 and body["provisions"] > 0 and body["chunks"] > 0
    assert 0 <= body["embedded"] <= body["chunks"]
