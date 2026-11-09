"""조문 조회. ID에 ':'가 들어가므로 쿼리 파라미터로 받는다."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.lang import today_kr
from app.schemas.provision import ProvisionOut, RelatedOut

router = APIRouter(prefix="/provisions", tags=["provisions"])

GET_SQL = text(
    """
    SELECT p.id, p.document_id, p.level, p.path, p.full_text_ko, p.effective_from, p.effective_to,
           d.title_ko, d.doc_type, d.status, d.source_url, d.reviewed, d.reviewed_by, d.reviewed_at,
           d.effective_from AS doc_from, d.effective_to AS doc_to,
           (SELECT c.content FROM chunks c
             WHERE c.jo_id = coalesce(p.jo_id, p.id) AND c.kind = 'summary' AND c.lang = 'vi' LIMIT 1) AS summary_vi,
           (SELECT c.content FROM chunks c
             WHERE c.jo_id = coalesce(p.jo_id, p.id) AND c.kind = 'summary' AND c.lang = 'ko' LIMIT 1) AS summary_ko
    FROM provisions p JOIN legal_documents d ON d.id = p.document_id
    WHERE p.id = :id
    """
)

RELATED_SQL = text(
    """
    SELECT e.dst_id AS other, e.rel, 'outgoing' AS direction, e.evidence
    FROM provision_edges e JOIN provisions p ON p.id = e.src_id
    WHERE p.id = :id OR p.jo_id = :id
    UNION ALL
    SELECT e.src_id AS other, e.rel, 'incoming' AS direction, e.evidence
    FROM provision_edges e JOIN provisions p ON p.id = e.dst_id
    WHERE p.id = :id OR p.jo_id = :id
    """
)


def _strip_header(summary: str | None) -> str | None:
    """요약 청크는 '[경로]\\n요약' 형식이다."""
    if not summary:
        return None
    return summary.split("\n", 1)[1] if summary.startswith("[") and "\n" in summary else summary


@router.get("", response_model=ProvisionOut)
async def get_provision(id: str = Query(..., examples=["출입국관리법:J25"]), session: AsyncSession = Depends(get_session)):
    r = (await session.execute(GET_SQL, {"id": id})).first()
    if r is None:
        raise HTTPException(404, "Provision not found.")
    today = today_kr()
    starts = [d for d in (r.effective_from, r.doc_from) if d]
    ends = [d for d in (r.effective_to, r.doc_to) if d]
    effective = r.status == "in_force" and all(d <= today for d in starts) and all(d > today for d in ends)
    return ProvisionOut(
        id=r.id,
        document_id=r.document_id,
        document_title=r.title_ko,
        doc_type=r.doc_type,
        level=r.level,
        number_label=r.path.rsplit(" › ", 1)[-1],
        path=r.path,
        full_text_ko=r.full_text_ko,
        summary_vi=_strip_header(r.summary_vi),
        summary_ko=_strip_header(r.summary_ko),
        effective=effective,
        effective_from=r.effective_from or r.doc_from,
        effective_to=r.effective_to or r.doc_to,
        status=r.status,
        source_url=r.source_url,
        reviewed=r.reviewed,
        reviewed_by=r.reviewed_by,
        reviewed_at=r.reviewed_at,
    )


@router.get("/related", response_model=list[RelatedOut])
async def related(id: str = Query(...), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(RELATED_SQL, {"id": id})).all()
    seen, out_rows = set(), []
    for r in rows:
        key = (r.other, r.rel, r.direction)
        if key not in seen:
            seen.add(key)
            out_rows.append(r)
    others = list({r.other for r in out_rows})
    paths = dict(
        (await session.execute(text("SELECT id, path FROM provisions WHERE id = ANY(:ids)"), {"ids": others})).all()
    ) if others else {}
    return [
        RelatedOut(provision_id=r.other, path=paths.get(r.other, r.other), rel=r.rel, direction=r.direction,
                   evidence=r.evidence)
        for r in out_rows
    ]
