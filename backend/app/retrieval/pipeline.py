"""검색 파이프라인: 하이브리드 검색 → 그래프 확장 → 조문 로드 → 리랭크."""

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.retrieval.graph import AMEND_RELS, GraphHit, expand, rel_priority
from app.retrieval.hybrid import hybrid_search
from app.retrieval.rerank import get_reranker

log = logging.getLogger("retrieval")

# 최종 컨텍스트(context_k) 중 그래프로 찾은 조에 떼어 두는 칸 수.
# 그래프 점수는 seed 점수에 가중치를 곱한 값이라 점수 경쟁만 시키면 항상 잘려 나간다.
GRAPH_SLOTS = 3
# 검색된 조의 개정 조문은 예산과 무관하게 넣되, 컨텍스트의 절반을 넘지는 않게 한다.
MAX_AMEND_SHARE = 0.5
# 리랭크 후보로 올릴 그래프 조 수 (개정 관계는 제한 없이 모두 올린다)
GRAPH_POOL = 20
# 선택된 조의 의무를 어기면 어떻게 되는지(벌칙·과태료) 답할 수 있도록 함께 넣는 벌칙 조 수
MAX_SANCTION = 2
SANCTION_SQL = text(
    """
    SELECT ps.jo_id AS sanction_id, pd.jo_id AS duty_id
    FROM provision_edges e
    JOIN provisions ps ON ps.id = e.src_id
    JOIN provisions pd ON pd.id = e.dst_id
    JOIN provisions pj ON pj.id = ps.jo_id
    WHERE e.rel = 'REFERENCES'
      AND pd.jo_id = ANY(:ids)
      AND ps.jo_id <> pd.jo_id
      AND (pj.path LIKE '%벌칙%' OR pj.path LIKE '%과태료%' OR pj.path LIKE '%범칙금%')
    """
)
# 체류자격 표(시행령 제12조 등)처럼 아주 긴 조는 통째로 넣으면 답변이 느리고 부정확해진다.
# 이 길이를 넘으면 검색에 걸린 항 + 기한·제재가 들어 있는 항만 넣는다.
MAX_ARTICLE_CHARS = 6000
SANCTION_HINTS = ("과태료", "범칙금", "벌금", "강제퇴거", "출국명령", "이내에", "기한")

HANG_SQL = text(
    """
    SELECT id, jo_id, number, full_text_ko FROM provisions
    WHERE jo_id = ANY(:ids) AND level = 'hang'
    ORDER BY jo_id, ordinal
    """
)


def _trim_article(full_text: str, heading: str, hangs: list, matched: set[str]) -> str:
    keep = [
        k for k in hangs
        if k.id in matched or any(m.startswith(f"{k.id}:") for m in matched)
        or any(h in k.full_text_ko[:400].lower() for h in SANCTION_HINTS)
    ]
    if not keep:
        return full_text[:MAX_ARTICLE_CHARS] + "\n[…]"
    body = "\n".join(k.full_text_ko for k in keep)
    return f"{heading}\n[… 관련 항만 발췌 …]\n{body}"

PROVISIONS_SQL = text(
    """
    SELECT p.id, p.path, p.full_text_ko, p.effective_from, p.effective_to,
           d.id AS document_id, d.title_ko, d.title_vi, d.doc_type, d.status,
           (SELECT c.content FROM chunks c
             WHERE c.jo_id = p.id AND c.kind = 'summary' AND c.lang = 'vi' LIMIT 1) AS summary_vi
    FROM provisions p JOIN legal_documents d ON d.id = p.document_id
    WHERE p.id = ANY(:ids)
    """
)


def add_sanctions(selected: list["ContextItem"], sanctions: list["ContextItem"], context_k: int) -> list["ContextItem"]:
    """선택된 조의 의무를 어겼을 때의 벌칙 조를 넣는다. 자리가 없으면 점수가 가장 낮은 조부터 밀어낸다."""
    have = {i.provision_id for i in selected}
    new = [i for i in sanctions if i.provision_id not in have][:MAX_SANCTION]
    if not new:
        return selected
    keep = sorted(selected, key=lambda i: -i.score)[: max(0, context_k - len(new))]
    kept = {i.provision_id for i in keep}
    return [i for i in selected if i.provision_id in kept] + new


@dataclass
class ContextItem:
    provision_id: str
    document_id: str
    title_ko: str
    title_vi: str | None
    doc_type: str
    path: str
    text_ko: str
    summary_vi: str | None
    effective_from: date | None
    status: str
    score: float
    source: str        # "search" | "graph: GUIDES ← …"


def _select(
    items: list[ContextItem],
    hits: dict[str, GraphHit],
    search_ids: set[str],
    context_k: int,
    graph_slots: int,
) -> list[ContextItem]:
    """최종 컨텍스트 선택: 검색 조 (context_k - graph_slots)개 + 그래프 조 예산.

    1) 선택된 검색 조를 개정·대체·폐지하는 조(역방향 AMENDS 등)는 항상 넣는다.
    2) 남은 그래프 예산은 관계 우선순위(개정 > GUIDES > REFERENCES) → 점수 순으로 채운다.
    3) 그래프 조가 모자라 남은 칸은 다시 검색 조로 채운다.
    """
    by_score = sorted(items, key=lambda i: -i.score)
    search = [i for i in by_score if i.provision_id in search_ids]
    graph_only = [i for i in by_score if i.provision_id in hits]
    reserved = min(graph_slots, context_k) if hits else 0

    selected = search[: context_k - reserved]
    chosen = {i.provision_id for i in selected}

    def is_mandatory(i: ContextItem) -> bool:
        h = hits[i.provision_id]
        return h.rel in AMEND_RELS and h.direction == "reverse" and h.origin in chosen

    mandatory = [i for i in graph_only if i.provision_id not in chosen and is_mandatory(i)]
    max_mandatory = max(reserved, int(context_k * MAX_AMEND_SHARE))
    mandatory = mandatory[:max_mandatory]
    must = {i.provision_id for i in mandatory}
    extra = [i for i in graph_only if i.provision_id not in chosen and i.provision_id not in must]
    extra.sort(key=lambda i: (rel_priority(hits[i.provision_id].rel), -i.score))
    graph_pick = mandatory + extra[: max(0, reserved - len(mandatory))]

    # 필수 개정 조가 예산을 넘으면 검색 조 꼬리를 밀어낸다
    room = context_k - len(graph_pick)
    selected = selected[:room]
    for it in graph_pick:
        h = hits[it.provision_id]
        it.source = f"graph: {h.via}"
    chosen = {i.provision_id for i in selected} | {i.provision_id for i in graph_pick}
    backfill = [i for i in search if i.provision_id not in chosen][: context_k - len(selected) - len(graph_pick)]
    return selected + backfill + graph_pick


async def retrieve(
    session: AsyncSession,
    queries_ko: list[str],
    original: str,
    as_of: date,
    domains: list[str] | None,
    include_samples: bool = False,
    on_stage=None,
    graph_slots: int | None = None,
) -> list[ContextItem]:
    s = get_settings()
    context_k = s.context_k
    graph_slots = GRAPH_SLOTS if graph_slots is None else graph_slots
    seeds, matched = await hybrid_search(
        session, queries_ko, original, as_of, domains, s.retrieval_k, include_samples=include_samples
    )
    if not seeds:
        return []
    top = max(seeds.values())
    seeds = {k: v / top for k, v in seeds.items()}

    if on_stage:
        await on_stage("expanding")
    graph = await expand(session, seeds, as_of, s.graph_hops, s.graph_frontier, include_samples=include_samples)

    # 리랭크 후보: 검색 상위 + 그래프 조 (개정 관계는 모두, 나머지는 우선순위·점수 상위 GRAPH_POOL개)
    seed_pool = [k for k, _ in sorted(seeds.items(), key=lambda x: -x[1])[: max(context_k * 3, 30)]]
    ranked_hits = sorted(graph.values(), key=lambda h: (rel_priority(h.rel), -h.score))
    graph_pool = [h for h in ranked_hits if h.rel in AMEND_RELS]
    graph_pool += [h for h in ranked_hits if h.rel not in AMEND_RELS][:GRAPH_POOL]
    hits = {h.jo_id: h for h in graph_pool}
    candidates: dict[str, tuple[float, str]] = {k: (seeds[k], "search") for k in seed_pool}
    for k, h in hits.items():
        if k not in candidates:
            candidates[k] = (h.score, f"graph: {h.via}")
    pool = list(candidates.items())
    rows = {r.id: r for r in (await session.execute(PROVISIONS_SQL, {"ids": [k for k, _ in pool]})).all()}
    long_ids = [pid for pid, r in rows.items() if len(r.full_text_ko) > MAX_ARTICLE_CHARS]
    hangs: dict[str, list] = {}
    if long_ids:
        for k in (await session.execute(HANG_SQL, {"ids": long_ids})).all():
            hangs.setdefault(k.jo_id, []).append(k)

    def article_text(r) -> str:
        if r.id not in hangs:
            return r.full_text_ko
        heading = r.full_text_ko.split("\n", 1)[0]
        return _trim_article(r.full_text_ko, heading, hangs[r.id], matched.get(r.id, set()))

    items = [
        ContextItem(
            provision_id=r.id,
            document_id=r.document_id,
            title_ko=r.title_ko,
            title_vi=r.title_vi,
            doc_type=r.doc_type,
            path=r.path,
            text_ko=article_text(r),
            summary_vi=r.summary_vi,
            effective_from=r.effective_from,
            status=r.status,
            score=score,
            source=source,
        )
        for pid, (score, source) in pool
        if (r := rows.get(pid))
    ]

    rerank_scores = await get_reranker().score(queries_ko[0] if queries_ko else original, [i.text_ko for i in items])
    if rerank_scores is not None:
        for item, sc in zip(items, rerank_scores):
            item.score = sc

    result = _select(items, hits, set(seed_pool), context_k, graph_slots)

    # 선택된 조를 위반했을 때의 벌칙·과태료 조 (예: 제98조 "제36조제1항에 따른 … 의무를 위반한 사람")
    duty_ids = [i.provision_id for i in result if i.source == "search"]
    pairs = (await session.execute(SANCTION_SQL, {"ids": duty_ids})).all() if duty_ids else []
    rank = {pid: n for n, pid in enumerate(duty_ids)}
    sanction_ids = list(dict.fromkeys(r.sanction_id for r in sorted(pairs, key=lambda r: rank.get(r.duty_id, 99))))
    if sanction_ids:
        srows = (await session.execute(PROVISIONS_SQL, {"ids": sanction_ids})).all()
        by_id = {r.id: r for r in srows if r.status == "in_force"}
        duty_of = {r.sanction_id: r.duty_id for r in pairs}
        sanctions = [
            ContextItem(r.id, r.document_id, r.title_ko, r.title_vi, r.doc_type, r.path, r.full_text_ko,
                        r.summary_vi, r.effective_from, r.status, 0.0, f"sanction: REFERENCES → {duty_of[sid]}")
            for sid in sanction_ids if (r := by_id.get(sid))
        ]
        result = add_sanctions(result, sanctions, context_k)
    added = [i for i in result if i.source.startswith("graph:")]
    if added:
        log.info("그래프 조 %d개 추가: %s", len(added), "; ".join(f"{i.provision_id} ({i.source})" for i in added))
    else:
        log.info("그래프 조 추가 없음 (후보 %d개)", len(hits))
    return result
