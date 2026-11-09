from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, Computed, Date, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id: Mapped[str] = mapped_column(Text, primary_key=True)            # '출입국관리법', '출입국관리법시행령'
    doc_type: Mapped[str] = mapped_column(Text)                         # law | decree | rule | guide
    title_ko: Mapped[str] = mapped_column(Text)
    title_vi: Mapped[str | None] = mapped_column(Text)
    short_names: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    issuer: Mapped[str | None] = mapped_column(Text)
    issued_date: Mapped[date | None] = mapped_column(Date)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)             # NULL = 현행
    status: Mapped[str] = mapped_column(Text, default="in_force")
    source_url: Mapped[str | None] = mapped_column(Text)
    domains: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    raw_hash: Mapped[str | None] = mapped_column(Text)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    preamble: Mapped[str | None] = mapped_column(Text)
    # 사람 검토 기록 (#14). 재적재해도 유지된다
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentRelation(Base):
    """문서 단위 관계 (시행령이 어떤 법률을 구체화하는지, 어떤 법률을 개정하는지)."""

    __tablename__ = "document_relations"

    src_doc: Mapped[str] = mapped_column(ForeignKey("legal_documents.id", ondelete="CASCADE"), primary_key=True)
    dst_doc: Mapped[str] = mapped_column(Text, primary_key=True)
    rel: Mapped[str] = mapped_column(Text, primary_key=True)            # GUIDES(시행령·시행규칙 → 상위 법) | AMENDS | REPLACES


class Provision(Base):
    __tablename__ = "provisions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)             # '출입국관리법:J10-2:H1'
    document_id: Mapped[str] = mapped_column(ForeignKey("legal_documents.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(Text)
    jo_id: Mapped[str | None] = mapped_column(Text, index=True)       # 소속 조 (조 자신이면 자기 ID)
    level: Mapped[str] = mapped_column(Text)                            # pyeon | jang | jeol | gwan | jo | hang | ho | mok
    number: Mapped[str] = mapped_column(Text)
    heading: Mapped[str | None] = mapped_column(Text)
    text_ko: Mapped[str] = mapped_column(Text, default="")              # 노드 자신의 본문
    full_text_ko: Mapped[str] = mapped_column(Text, default="")         # 하위 항·호 포함 전체
    path: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    provision_id: Mapped[str] = mapped_column(ForeignKey("provisions.id", ondelete="CASCADE"))
    jo_id: Mapped[str] = mapped_column(Text, index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("legal_documents.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)                             # original | summary
    lang: Mapped[str] = mapped_column(Text)                             # vi | ko
    content: Mapped[str] = mapped_column(Text)
    tokens: Mapped[str | None] = mapped_column(Text)                    # 검색 토큰 (한글 2-gram + 어절)
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('simple'::regconfig, coalesce(tokens, content))"))
    embedding = mapped_column(Vector(1536), nullable=True)
    domains: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)


class ProvisionEdge(Base):
    __tablename__ = "provision_edges"

    src_id: Mapped[str] = mapped_column(ForeignKey("provisions.id", ondelete="CASCADE"), primary_key=True)
    dst_id: Mapped[str] = mapped_column(ForeignKey("provisions.id", ondelete="CASCADE"), primary_key=True, index=True)
    rel: Mapped[str] = mapped_column(Text, primary_key=True)            # REFERENCES | GUIDES | AMENDS | REPLACES | REPEALS
    evidence: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text, default="rule")           # rule | llm | manual
    confidence: Mapped[float] = mapped_column(Float, default=1.0)


class UnresolvedReference(Base):
    """해석하지 못한 참조. 사람이 검토하거나 대상 법령을 추가 적재할 때 쓴다."""

    __tablename__ = "unresolved_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    src_id: Mapped[str] = mapped_column(ForeignKey("provisions.id", ondelete="CASCADE"))
    evidence: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
