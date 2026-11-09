"""초기 스키마: 법령 지식베이스 + 서류 분석 건 + 미해결 질문·사용량 기록

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# asyncpg는 한 번에 여러 문장을 실행하지 못하므로 문장별로 나눠 둔다
UPGRADE = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    """
    CREATE TABLE legal_documents (
        id              TEXT PRIMARY KEY,
        doc_type        TEXT NOT NULL CHECK (doc_type IN ('law', 'decree', 'rule', 'guide')),
        title_ko        TEXT NOT NULL,
        title_vi        TEXT,
        short_names     TEXT[] NOT NULL DEFAULT '{}',
        issuer          TEXT,
        issued_date     DATE,
        effective_from  DATE,
        effective_to    DATE,
        status          TEXT NOT NULL DEFAULT 'in_force' CHECK (status IN ('in_force', 'not_yet', 'repealed')),
        source_url      TEXT,
        domains         TEXT[] NOT NULL DEFAULT '{}',
        raw_hash        TEXT,
        is_sample       BOOLEAN NOT NULL DEFAULT false,
        preamble        TEXT,
        reviewed        BOOLEAN NOT NULL DEFAULT false,
        reviewed_by     TEXT,
        reviewed_at     TIMESTAMPTZ,
        review_note     TEXT,
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE document_relations (
        src_doc  TEXT NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
        dst_doc  TEXT NOT NULL,
        rel      TEXT NOT NULL,
        PRIMARY KEY (src_doc, dst_doc, rel)
    )
    """,
    """
    CREATE TABLE provisions (
        id              TEXT PRIMARY KEY,
        document_id     TEXT NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
        parent_id       TEXT,
        jo_id           TEXT,
        level           TEXT NOT NULL,
        number          TEXT NOT NULL,
        heading         TEXT,
        text_ko         TEXT NOT NULL DEFAULT '',
        full_text_ko    TEXT NOT NULL DEFAULT '',
        path            TEXT NOT NULL,
        ordinal         INTEGER NOT NULL,
        effective_from  DATE,
        effective_to    DATE
    )
    """,
    "CREATE INDEX ix_provisions_document_id ON provisions (document_id)",
    "CREATE INDEX ix_provisions_jo_id ON provisions (jo_id)",
    """
    CREATE TABLE chunks (
        id            BIGSERIAL PRIMARY KEY,
        provision_id  TEXT NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
        jo_id         TEXT NOT NULL,
        document_id   TEXT NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
        kind          TEXT NOT NULL,
        lang          TEXT NOT NULL,
        content       TEXT NOT NULL,
        tokens        TEXT,
        tsv           TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, coalesce(tokens, content))) STORED,
        embedding     vector(1536),
        domains       TEXT[] NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX ix_chunks_jo_id ON chunks (jo_id)",
    "CREATE INDEX ix_chunks_tsv ON chunks USING gin (tsv)",
    "CREATE INDEX ix_chunks_domains ON chunks USING gin (domains)",
    "CREATE INDEX ix_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops)",
    """
    CREATE TABLE provision_edges (
        src_id      TEXT NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
        dst_id      TEXT NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
        rel         TEXT NOT NULL,
        evidence    TEXT,
        method      TEXT NOT NULL DEFAULT 'rule',
        confidence  REAL NOT NULL DEFAULT 1.0,
        PRIMARY KEY (src_id, dst_id, rel)
    )
    """,
    "CREATE INDEX ix_provision_edges_dst_id ON provision_edges (dst_id)",
    """
    CREATE TABLE unresolved_references (
        id        BIGSERIAL PRIMARY KEY,
        src_id    TEXT NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
        evidence  TEXT NOT NULL,
        reason    TEXT NOT NULL
    )
    """,
    # 서류 분석 건 (핵심 대상). 원본 파일은 저장하지 않고, 식별정보를 마스킹한 추출 텍스트만 둔다
    """
    CREATE TABLE analyses (
        id            UUID PRIMARY KEY,
        client_id     TEXT NOT NULL,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        lang          TEXT NOT NULL,
        filename      TEXT NOT NULL,
        mime          TEXT,
        file_size     INTEGER,
        page_count    INTEGER,
        text          TEXT NOT NULL,
        masked_count  INTEGER NOT NULL DEFAULT 0,
        status        TEXT NOT NULL CHECK (status IN
                        ('uploaded', 'questions', 'analyzing', 'failed', 'review', 'done', 'canceled')),
        stage         TEXT,
        job_id        TEXT,
        intake        JSONB,
        facts         JSONB,
        answers       JSONB,
        result        JSONB,
        checklist     JSONB,
        error         TEXT
    )
    """,
    "CREATE INDEX ix_analyses_client ON analyses (client_id, created_at DESC)",
    """
    CREATE TABLE open_questions (
        id           BIGSERIAL PRIMARY KEY,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        session_id   TEXT,
        analysis_id  UUID,
        source       TEXT NOT NULL CHECK (source IN ('chat', 'analysis')),
        question     TEXT NOT NULL,
        resolved     BOOLEAN NOT NULL DEFAULT false,
        resolved_at  TIMESTAMPTZ
    )
    """,
    "CREATE INDEX ix_open_questions_session ON open_questions (session_id, resolved)",
    "CREATE INDEX ix_open_questions_analysis ON open_questions (analysis_id, resolved)",
    """
    CREATE TABLE usage_log (
        id               BIGSERIAL PRIMARY KEY,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
        kind             TEXT NOT NULL CHECK (kind IN ('chat', 'analysis')),
        ref              TEXT,
        model_breakdown  JSONB NOT NULL DEFAULT '{}'::jsonb,
        input_tokens     INTEGER NOT NULL DEFAULT 0,
        output_tokens    INTEGER NOT NULL DEFAULT 0,
        cost_usd         NUMERIC(12, 6) NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX ix_usage_log_created_at ON usage_log (created_at DESC)",
]

DOWNGRADE = [
    "DROP TABLE IF EXISTS usage_log",
    "DROP TABLE IF EXISTS open_questions",
    "DROP TABLE IF EXISTS analyses",
    "DROP TABLE IF EXISTS unresolved_references",
    "DROP TABLE IF EXISTS provision_edges",
    "DROP TABLE IF EXISTS chunks",
    "DROP TABLE IF EXISTS provisions",
    "DROP TABLE IF EXISTS document_relations",
    "DROP TABLE IF EXISTS legal_documents",
]


def upgrade() -> None:
    for stmt in UPGRADE:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in DOWNGRADE:
        op.execute(stmt)
