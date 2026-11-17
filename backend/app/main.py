import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import chat, documents, provisions, questions, search
from app.core.config import get_settings
from app.core.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = get_settings()
app = FastAPI(title="다문화가족 체류 AI 도우미", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (chat.router, documents.router, provisions.router, search.router, questions.router, questions.usage_router):
    app.include_router(r, prefix="/api/v1")


@app.get("/health")
async def health():
    async with SessionLocal() as s:
        docs = (await s.execute(text("SELECT count(*) FROM legal_documents"))).scalar_one()
        provs = (await s.execute(text("SELECT count(*) FROM provisions"))).scalar_one()
        chunks = (await s.execute(text("SELECT count(*), count(embedding) FROM chunks"))).one()
        laws = (await s.execute(text(
            "SELECT count(*) FILTER (WHERE version_status = 'outdated'), "
            "count(*) FILTER (WHERE version_status = 'unknown' OR version_checked_at IS NULL "
            "  OR version_checked_at < now() - make_interval(days => :days)), min(version_checked_at) "
            "FROM legal_documents WHERE NOT is_sample"
        ), {"days": settings.law_version_max_age_days})).one()
    return {
        "status": "ok",
        "documents": docs,
        "provisions": provs,
        "chunks": chunks[0],
        "embedded": chunks[1],
        "llm_fake": settings.llm_fake,
        # 법령 판 확인 (python -m ingest versions). 새 판이 시행 중인 법령 수, 확인 못 했거나 확인이 오래된 법령 수,
        # 가장 오래된 확인 시각
        "laws_outdated": laws[0],
        "laws_unchecked": laws[1],
        "laws_checked_at": laws[2],
    }
