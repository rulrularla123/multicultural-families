"""추출한 참조를 실제 조문 ID로 해석해 그래프 엣지를 만든다."""

from dataclasses import dataclass

from ingest.relations.patterns import (
    UNKNOWN_PREFIX,
    AliasIndex,
    DocContext,
    extract_local_refs,
    extract_refs,
)


@dataclass(frozen=True)
class DocMeta:
    id: str
    title_ko: str
    short_names: tuple[str, ...]
    parent_law: str | None = None      # 시행령·시행규칙이 구체화하는 법률 ("법 제n조")
    parent_decree: str | None = None   # 시행규칙이 함께 구체화하는 시행령 ("영 제n조")


@dataclass(frozen=True)
class SourceProvision:
    id: str
    document_id: str
    jo_id: str | None
    text: str                   # 노드 자신의 본문 (조는 제목 포함)
    context: str = ""           # 상위 노드의 제목·도입문
    hang_id: str | None = None  # 호·목이면 소속 항 ("제1호"처럼 항 안을 가리킬 때)


@dataclass(frozen=True)
class Edge:
    src_id: str
    dst_id: str
    rel: str
    evidence: str
    method: str = "rule"
    confidence: float = 1.0


@dataclass(frozen=True)
class Unresolved:
    src_id: str
    evidence: str
    reason: str


def build_alias_index(docs: list[DocMeta]) -> AliasIndex:
    aliases: dict[str, str] = {}
    for d in docs:
        for name in (d.title_ko, *d.short_names):
            aliases[name] = d.id
    return AliasIndex(aliases)


def target_id(doc_id: str, jo: str, hang: str | None, ho: str | None, mok: str | None, known: set[str]) -> str | None:
    """가장 구체적인 ID부터 시도하고, 없으면 상위(조)로 물러난다. 항 없이 호가 바로 오는 조도 있다."""
    base = f"{doc_id}:J{jo}"
    candidates = []
    if hang and ho and mok:
        candidates.append(f"{base}:H{hang}:O{ho}:M{mok}")
    if hang and ho:
        candidates.append(f"{base}:H{hang}:O{ho}")
    if ho and mok:
        candidates.append(f"{base}:O{ho}:M{mok}")
    if ho and not hang:
        candidates.append(f"{base}:O{ho}")
    if hang:
        candidates.append(f"{base}:H{hang}")
    candidates.append(base)
    return next((c for c in candidates if c in known), None)


def resolve_edges(
    provisions: list[SourceProvision], docs: list[DocMeta], known_ids: set[str]
) -> tuple[list[Edge], list[Unresolved]]:
    meta = {d.id: d for d in docs}
    aliases = build_alias_index(docs)
    edges: dict[tuple[str, str, str], Edge] = {}
    unresolved: list[Unresolved] = []

    for p in provisions:
        if not p.text:
            continue
        doc = meta.get(p.document_id)
        ctx = DocContext(p.document_id, doc.parent_law if doc else None, doc.parent_decree if doc else None)
        parents = {x for x in (ctx.parent_law, ctx.parent_decree) if x}

        for ref in extract_refs(p.text, ctx, aliases):
            if ref.target_doc and ref.target_doc.startswith(UNKNOWN_PREFIX):
                unresolved.append(Unresolved(p.id, ref.evidence, f"대상 법령 미적재: {ref.target_doc[1:]}"))
                continue
            target_doc = ref.target_doc or p.document_id
            dst = target_id(target_doc, ref.jo, ref.hang, ref.ho, ref.mok, known_ids)
            if dst is None:
                reason = "대상 법령 미적재" if target_doc not in meta else "대상 조문 없음"
                unresolved.append(Unresolved(p.id, ref.evidence, f"{reason}: {target_doc} 제{ref.jo}조"))
                continue
            if dst == p.id or (p.jo_id and dst == p.jo_id):
                continue
            # 시행령·시행규칙이 상위 법령 조문을 가리키면 그 조문을 구체화하는 관계로 본다
            rel = "GUIDES" if target_doc in parents else ref.rel
            edges.setdefault((p.id, dst, rel), Edge(p.id, dst, rel, ref.evidence))

        if p.jo_id:
            jo = p.jo_id.rsplit(":J", 1)[1]
            for hang, ho, evidence in extract_local_refs(p.text):
                dst = target_id(p.document_id, jo, hang, ho, None, known_ids)
                if dst and dst != p.id and not p.id.startswith(f"{dst}:"):
                    edges.setdefault((p.id, dst, "REFERENCES"), Edge(p.id, dst, "REFERENCES", evidence))

    return list(edges.values()), unresolved
