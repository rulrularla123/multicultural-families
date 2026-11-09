"""적재 파이프라인: 원본 → 조문 트리 → 청크 → 관계 그래프 → (선택) 쉬운 요약 → 임베딩."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import vector_literal
from app.llm import complete, embed_texts
from app.models.law import (
    Chunk,
    DocumentRelation,
    LegalDocument,
    Provision,
    ProvisionEdge,
    UnresolvedReference,
)
from ingest.chunker import chunk_document
from ingest.loader import RawDocument
from ingest.parsers.structure import parse_law
from ingest.relations.resolver import DocMeta, SourceProvision, resolve_edges

log = logging.getLogger("ingest")


async def load_documents(session: AsyncSession, docs: list[RawDocument], force: bool = False) -> None:
    for raw in docs:
        existing = await session.get(LegalDocument, raw.id)
        if existing and existing.raw_hash == raw.raw_hash and not force:
            log.info("변경 없음, 건너뜀: %s", raw.id)
            continue
        # 검토 기록은 원문 재적재와 무관하므로 옮겨 둔다
        review = (
            {k: getattr(existing, k) for k in ("reviewed", "reviewed_by", "reviewed_at", "review_note")}
            if existing else {}
        )
        if existing:
            session.expunge(existing)
        parsed = parse_law(raw.text, raw.id, raw.meta["title_ko"])
        for w in parsed.warnings:
            log.warning("[%s] %s", raw.id, w)

        # 문서를 지우면 조문·청크·엣지가 CASCADE로 함께 지워진다
        await session.execute(delete(LegalDocument).where(LegalDocument.id == raw.id))
        m = raw.meta
        session.add(
            LegalDocument(
                id=raw.id,
                doc_type=m["doc_type"],
                title_ko=m["title_ko"],
                title_vi=m.get("title_vi"),
                short_names=m.get("short_names", []),
                issuer=m.get("issuer"),
                issued_date=raw.date("issued_date"),
                effective_from=raw.date("effective_from"),
                effective_to=raw.date("effective_to"),
                status=m["status"],
                source_url=m.get("source_url"),
                domains=m.get("domains", []),
                raw_hash=raw.raw_hash,
                is_sample=m.get("is_sample", False),
                preamble=parsed.preamble,
                **review,
            )
        )
        await session.flush()

        rels = [(raw.id, d, "GUIDES") for d in m.get("guides", [])]
        if rels:
            await session.execute(
                insert(DocumentRelation), [{"src_doc": s, "dst_doc": d, "rel": r} for s, d, r in rels]
            )

        rows = []
        for n in parsed.nodes():
            jo = n.jo()
            rows.append(
                {
                    "id": n.id,
                    "document_id": raw.id,
                    "parent_id": n.parent.id if n.parent else None,
                    "jo_id": jo.id if jo else None,
                    "level": n.level,
                    "number": n.number,
                    "heading": n.heading or None,
                    "text_ko": n.text,
                    "full_text_ko": n.render(),
                    "path": n.path(parsed.title),
                    "ordinal": n.ordinal,
                    "effective_from": raw.date("effective_from"),
                    "effective_to": raw.date("effective_to"),
                }
            )
        await session.execute(insert(Provision), rows)

        chunks = [
            {
                "provision_id": c.provision_id,
                "jo_id": c.jo_id,
                "document_id": raw.id,
                "kind": "original",
                "lang": "ko",
                "content": c.content,
                "tokens": c.tokens,
                "domains": m.get("domains", []),
            }
            for c in chunk_document(parsed)
        ]
        if chunks:
            await session.execute(insert(Chunk), chunks)
        await session.commit()
        log.info("적재 완료: %s (조 %d개, 청크 %d개)", raw.id, len(parsed.jos()), len(chunks))


def doc_metas(docs, doc_rels) -> list[DocMeta]:
    """문서 행 + GUIDES 관계 → 참조 해석용 메타 (시행령의 "법", 시행규칙의 "영")"""
    types = {d.id: d.doc_type for d in docs}
    out = []
    for d in docs:
        parents = [r.dst_doc for r in doc_rels if r.src_doc == d.id and r.rel == "GUIDES"]
        out.append(DocMeta(
            id=d.id,
            title_ko=d.title_ko,
            short_names=tuple(d.short_names or []),
            parent_law=next((x for x in parents if types.get(x) == "law"), None),
            parent_decree=next((x for x in parents if types.get(x) == "decree"), None),
        ))
    return out


def source_provisions(rows) -> list[SourceProvision]:
    """조는 제목을 본문 앞에 붙이고(개정 문서는 제목에 대상 조가 있다), 상위 노드 문맥을 함께 넘긴다."""
    by_id = {r.id: r for r in rows}

    def own_text(r) -> str:
        return f"{r.heading}\n{r.text_ko}" if r.level == "jo" and r.heading else (r.text_ko or "")

    out = []
    for r in rows:
        ctx, parent = [], by_id.get(r.parent_id) if r.parent_id else None
        while parent is not None and len(ctx) < 3:
            ctx.append(own_text(parent)[:600])
            parent = by_id.get(parent.parent_id) if parent.parent_id else None
        out.append(SourceProvision(r.id, r.document_id, r.jo_id, own_text(r), "\n".join(reversed(ctx))))
    return out


async def rebuild_relations(session: AsyncSession) -> tuple[int, int]:
    """전체 문서를 대상으로 규칙 기반 엣지를 다시 만든다. 수동(manual) 엣지는 보존한다."""
    docs = (await session.execute(select(LegalDocument))).scalars().all()
    doc_rels = (await session.execute(select(DocumentRelation))).scalars().all()
    metas = doc_metas(docs, doc_rels)
    rows = (
        await session.execute(
            select(Provision.id, Provision.document_id, Provision.jo_id, Provision.parent_id, Provision.level,
                   Provision.heading, Provision.text_ko)
        )
    ).all()
    provisions = source_provisions(rows)
    edges, unresolved = resolve_edges(provisions, metas, {p.id for p in provisions})

    await session.execute(delete(ProvisionEdge).where(ProvisionEdge.method != "manual"))
    await session.execute(delete(UnresolvedReference))
    if edges:
        await session.execute(
            insert(ProvisionEdge),
            [
                {
                    "src_id": e.src_id,
                    "dst_id": e.dst_id,
                    "rel": e.rel,
                    "evidence": e.evidence,
                    "method": e.method,
                    "confidence": e.confidence,
                }
                for e in edges
            ],
        )
    if unresolved:
        await session.execute(
            insert(UnresolvedReference),
            [{"src_id": u.src_id, "evidence": u.evidence, "reason": u.reason} for u in unresolved],
        )
    await session.commit()
    log.info("관계 재구성: 엣지 %d개, 미해결 참조 %d개", len(edges), len(unresolved))
    return len(edges), len(unresolved)


async def embed_missing(session: AsyncSession, batch: int = 64) -> int:
    from app.core.config import get_settings

    if get_settings().llm_fake:
        raise RuntimeError("LLM_FAKE=true 상태에서는 임베딩을 저장하지 않습니다 (가짜 벡터가 DB에 남음).")
    total = 0
    while True:
        rows = (
            await session.execute(
                select(Chunk.id, Chunk.content).where(Chunk.embedding.is_(None)).order_by(Chunk.id).limit(batch)
            )
        ).all()
        if not rows:
            break
        vectors = await embed_texts([r.content for r in rows])
        await session.execute(
            text("UPDATE chunks SET embedding = CAST(:v AS vector) WHERE id = :id"),
            [{"id": r.id, "v": vector_literal(v)} for r, v in zip(rows, vectors)],
        )
        await session.commit()
        total += len(rows)
        log.info("임베딩 %d개 완료", total)
    return total


SUMMARY_INSTRUCTIONS = {
    "vi": (
        "You summarize one article of Korean immigration/residence law for Vietnamese marriage migrants living "
        "in Korea. Write 2-4 sentences in plain Vietnamese. Keep every number, deadline, amount and condition "
        "exactly. Put the key Korean legal term in parentheses after its Vietnamese translation the first time, "
        "e.g. gia hạn thời gian lưu trú (체류기간 연장허가). Do not add information that is not in the article."
    ),
    "ko": (
        "한국 출입국·체류 법령 조문 하나를 법률 지식이 없는 사람도 이해하도록 쉬운 한국어 2~4문장으로 요약한다. "
        "숫자·기한·금액·조건은 그대로 둔다. 조문에 없는 내용은 덧붙이지 않는다."
    ),
}


async def summarize_missing(session: AsyncSession, lang: str = "vi", concurrency: int = 16) -> int:
    """조마다 쉬운 요약 청크를 만든다. 베트남어 요약은 베트남어 질문의 검색 재현율을 높인다."""
    from app.core.config import get_settings

    if get_settings().llm_fake:
        raise RuntimeError("LLM_FAKE=true 상태에서는 요약을 저장하지 않습니다.")
    instructions = SUMMARY_INSTRUCTIONS[lang]
    rows = (
        await session.execute(
            text(
                """
                SELECT p.id, p.document_id, p.path, p.full_text_ko, d.domains
                FROM provisions p JOIN legal_documents d ON d.id = p.document_id
                WHERE p.level = 'jo' AND p.full_text_ko NOT LIKE '%삭제 <%'
                  AND NOT EXISTS (SELECT 1 FROM chunks c
                                  WHERE c.jo_id = p.id AND c.kind = 'summary' AND c.lang = :lang)
                ORDER BY p.document_id, p.ordinal
                """
            ),
            {"lang": lang},
        )
    ).all()
    sem = asyncio.Semaphore(concurrency)

    async def one(r):
        async with sem:
            summary = await complete(instructions, f"{r.path}\n\n{r.full_text_ko}")
            return r, summary.strip()

    done = 0
    for i in range(0, len(rows), 50):
        results = await asyncio.gather(*(one(r) for r in rows[i : i + 50]))
        await session.execute(
            insert(Chunk),
            [
                {
                    "provision_id": r.id,
                    "jo_id": r.id,
                    "document_id": r.document_id,
                    "kind": "summary",
                    "lang": lang,
                    "content": f"[{r.path}]\n{s}",
                    "tokens": None,
                    "domains": r.domains,
                }
                for r, s in results
            ],
        )
        await session.commit()
        done += len(results)
        log.info("요약(%s) %d/%d", lang, done, len(rows))
    return done


async def set_review(
    session: AsyncSession, doc_id: str, by: str | None, note: str | None = None, unset: bool = False
) -> LegalDocument:
    """문서 검토 표시(#14). unset이면 검토 기록을 지운다."""
    doc = await session.get(LegalDocument, doc_id)
    if doc is None:
        raise LookupError(f"문서 없음: {doc_id}")
    if unset:
        doc.reviewed, doc.reviewed_by, doc.reviewed_at, doc.review_note = False, None, None, note
    else:
        if not by:
            raise ValueError("--by 필요")
        doc.reviewed, doc.reviewed_by, doc.reviewed_at = True, by, datetime.now(UTC)
        doc.review_note = note
    await session.commit()
    return doc


async def list_reviews(session: AsyncSession) -> list[LegalDocument]:
    q = select(LegalDocument).where(~LegalDocument.is_sample).order_by(LegalDocument.reviewed, LegalDocument.id)
    return list((await session.execute(q)).scalars().all())
