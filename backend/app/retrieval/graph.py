"""GraphRAG 확장: 검색된 조에서 참조·위임·개정 관계를 따라 연관 조를 추가한다."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# (관계, 방향) → 가중치. forward = src→dst, reverse = dst→src
# 예: 법률 조(dst)에서 그것을 구체화하는 시행령 조(src)로 가는 것은 GUIDES reverse
WEIGHTS: dict[tuple[str, str], float] = {
    ("REFERENCES", "forward"): 0.7,
    ("REFERENCES", "reverse"): 0.5,
    ("GUIDES", "reverse"): 0.9,
    ("GUIDES", "forward"): 0.7,
    ("AMENDS", "reverse"): 0.8,
    ("AMENDS", "forward"): 0.6,
    ("REPLACES", "reverse"): 0.8,
    ("REPEALS", "reverse"): 0.8,
}

EDGES_SQL = text(
    """
    SELECT e.rel, e.confidence, e.evidence, ps.jo_id AS src_jo, pd.jo_id AS dst_jo
    FROM provision_edges e
    JOIN provisions ps ON ps.id = e.src_id
    JOIN provisions pd ON pd.id = e.dst_id
    WHERE ps.jo_id = ANY(:ids) OR pd.jo_id = ANY(:ids)
    """
)

VALID_SQL = text(
    """
    SELECT p.id FROM provisions p JOIN legal_documents d ON d.id = p.document_id
    WHERE p.id = ANY(:ids)
      AND (p.effective_from IS NULL OR p.effective_from <= :as_of)
      AND (p.effective_to IS NULL OR p.effective_to > :as_of)
      AND d.status = 'in_force'
      AND (:include_samples OR NOT d.is_sample)
    """
)


# 컨텍스트 예산을 나눌 때의 관계 우선순위 (작을수록 먼저). 개정·대체·폐지는 현행 법을 바꾸므로 최우선.
AMEND_RELS = ("AMENDS", "REPLACES", "REPEALS")
REL_PRIORITY: dict[str, int] = {"AMENDS": 0, "REPLACES": 0, "REPEALS": 0, "GUIDES": 1, "REFERENCES": 2}


def rel_priority(rel: str) -> int:
    return REL_PRIORITY.get(rel, 3)


@dataclass
class GraphHit:
    jo_id: str
    score: float
    via: str        # 예: "GUIDES ← 01/2024/QH-TEST:D4"
    rel: str = ""
    origin: str = ""   # 이 조로 건너온 출발 조 (via의 오른쪽)
    hop: int = 1
    direction: str = "forward"   # reverse = 출발 조를 가리키는 조 (예: 출발 조를 개정하는 조)

    def key(self) -> tuple[int, float]:
        """같은 조에 여러 경로로 도달하면 관계 우선순위 → 점수 순으로 대표 경로를 고른다."""
        return (-rel_priority(self.rel), self.score)


async def expand(
    session: AsyncSession,
    seeds: dict[str, float],
    as_of: date,
    hops: int,
    frontier_size: int,
    include_samples: bool = False,
) -> dict[str, GraphHit]:
    """seeds(조 ID → 점수)에서 관계를 따라 이웃 조를 찾는다.

    엣지는 항·호 단위 ID(X:D7:K3)끼리 이어져 있으므로 양 끝을 소속 조(jo_id)로 올려 비교한다.
    개정 관계(AMENDS/REPLACES/REPEALS)는 seed 자신이 개정 조문이어도 기록한다 —
    검색 점수가 낮아 컨텍스트에서 잘리더라도 개정 대상 조와 함께 반드시 넣기 위해서다.
    """
    found: dict[str, GraphHit] = {}
    frontier = dict(sorted(seeds.items(), key=lambda x: -x[1])[:frontier_size])

    for hop in range(1, hops + 1):
        if not frontier:
            break
        rows = (await session.execute(EDGES_SQL, {"ids": list(frontier)})).all()
        nxt: dict[str, GraphHit] = {}
        for r in rows:
            if not r.src_jo or not r.dst_jo or r.src_jo == r.dst_jo:
                continue
            for origin, target, direction in ((r.src_jo, r.dst_jo, "forward"), (r.dst_jo, r.src_jo, "reverse")):
                if origin not in frontier:
                    continue
                if target in seeds and not (hop == 1 and r.rel in AMEND_RELS):
                    continue
                w = WEIGHTS.get((r.rel, direction))
                if not w:
                    continue
                score = frontier[origin] * w * r.confidence
                arrow = "→" if direction == "forward" else "←"
                hit = GraphHit(target, score, f"{r.rel} {arrow} {origin}", r.rel, origin, hop, direction)
                if target not in nxt or nxt[target].key() < hit.key():
                    nxt[target] = hit
        nxt = {k: v for k, v in nxt.items() if k not in found or found[k].key() < v.key()}
        # 기준일에 효력이 없는 조는 결과에서도, 다음 hop의 경유지로도 쓰지 않는다
        # (예: 시행 전 개정 조문을 거쳐 무관한 조를 끌어오지 않도록)
        if nxt:
            valid_now = {
                r.id
                for r in (
                    await session.execute(
                        VALID_SQL, {"ids": list(nxt), "as_of": as_of, "include_samples": include_samples}
                    )
                ).all()
            }
            nxt = {k: v for k, v in nxt.items() if k in valid_now}
        found.update(nxt)
        # seed는 이미 frontier로 쓰였으므로 다음 hop에서는 새로 찾은 조만 확장한다
        fresh = {k: v for k, v in nxt.items() if k not in seeds}
        frontier = {k: v.score for k, v in sorted(fresh.items(), key=lambda x: -x[1].score)[:frontier_size]}

    if not found:
        return {}
    valid = {
        r.id
        for r in (
            await session.execute(
                VALID_SQL, {"ids": list(found), "as_of": as_of, "include_samples": include_samples}
            )
        ).all()
    }
    return {k: v for k, v in found.items() if k in valid}
