"""서류 분석 건: 업로드 → 개인화 질문(필수) → 분석(백그라운드) → 결과 확인 → 체크리스트 완료.

상태: uploaded → questions → analyzing → review ↔ done, analyzing → failed → analyzing, 진행 중 → canceled.
- 분석 건은 브라우저 익명 ID(client_id)로 구분한다. 다른 ID의 건은 없는 건처럼 다룬다(404).
- 업로드 직후 추출 텍스트의 식별정보를 마스킹해서 저장한다. 원본 파일은 저장하지 않는다.
- 분석은 job_id를 붙여 돌리고, 결과를 저장할 때 job_id와 상태가 그대로일 때만 저장한다
  (취소·재시도 뒤 늦게 온 결과는 버린다).
"""

import asyncio
import json
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import llm
from app.common.identity_patterns import mask
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.lang import Lang, t, today_kr
from app.documents import facts as fx
from app.documents.analyze import DocumentAnalysis, run_analysis
from app.documents.extract import extract_text
from app.documents.intake import Intake, run_intake
from app.documents.segment import Segment, segment_document
from app.generation.answer import Citation
from app.generation.verify import check_citation, lookup, quote_in_text
from app.retrieval.pipeline import retrieve

log = logging.getLogger(__name__)
STAGES = ["extracted", "searching", "analyzing", "verifying"]
ACTIVE = ("uploaded", "questions", "analyzing", "review")
_tasks: set[asyncio.Task] = set()


class AnalysisError(Exception):
    """입력 오류 (422)."""


class AnalysisNotFound(AnalysisError):
    pass


class AnalysisStateError(AnalysisError):
    """현재 상태에서는 할 수 없는 요청 (409)."""


class AnalysisLLMError(AnalysisError):
    """LLM 호출 실패 (502)."""


class MissingAnswers(AnalysisError):
    def __init__(self, message: str, missing: list[str]):
        super().__init__(message)
        self.missing = missing


def _doc_facts(intake: dict) -> list[dict]:
    return fx.initial_facts(intake.get("facts") or [])


def _row_view(r) -> dict:
    intake = r.intake or {}
    return {
        "id": str(r.id),
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
        "lang": r.lang,
        "filename": r.filename,
        "file_size": r.file_size,
        "page_count": r.page_count,
        "masked_count": r.masked_count,
        "status": r.status,
        "stage": r.stage,
        "error": r.error,
        "title": intake.get("title"),
        "doc_type_label": intake.get("doc_type_label"),
        "intake": {k: intake.get(k) for k in ("doc_kind", "doc_type_label", "title", "summary", "basic_info",
                                               "questions")} if intake else None,
        "facts": fx.public(r.facts or []),
        "answers": r.answers,
        "result": r.result,
        "checklist": r.checklist,
    }


async def _row(session: AsyncSession, client_id: str, analysis_id: str, lock: bool = False):
    try:
        aid = uuid.UUID(str(analysis_id))
    except ValueError:
        raise AnalysisNotFound("Analysis not found.") from None
    sql = "SELECT * FROM analyses WHERE id = :id AND client_id = :cid" + (" FOR UPDATE" if lock else "")
    r = (await session.execute(text(sql), {"id": aid, "cid": client_id})).first()
    if r is None:
        raise AnalysisNotFound("Analysis not found.")
    return r


async def get_analysis(session: AsyncSession, client_id: str, analysis_id: str) -> dict:
    return _row_view(await _row(session, client_id, analysis_id))


async def list_analyses(session: AsyncSession, client_id: str, limit: int = 30) -> list[dict]:
    rows = (await session.execute(
        text("SELECT * FROM analyses WHERE client_id = :cid ORDER BY created_at DESC LIMIT :n"),
        {"cid": client_id, "n": limit},
    )).all()
    out = []
    for r in rows:
        v = _row_view(r)
        out.append({k: v[k] for k in ("id", "created_at", "filename", "status", "title", "doc_type_label")}
                   | {"counts": (v["result"] or {}).get("counts")})
    return out


async def delete_analysis(session: AsyncSession, client_id: str, analysis_id: str) -> None:
    await _row(session, client_id, analysis_id)
    await session.execute(text("DELETE FROM analyses WHERE id = :id AND client_id = :cid"),
                          {"id": uuid.UUID(str(analysis_id)), "cid": client_id})
    await session.commit()


async def create_analysis(
    session: AsyncSession, client_id: str, filename: str, mime: str | None, data: bytes, lang: Lang
) -> dict:
    extracted = extract_text(filename, mime, data, lang)
    masked, masked_count = mask(extracted.text)
    analysis_id = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO analyses (id, client_id, lang, filename, mime, file_size, page_count, text, masked_count,
                                  status, stage)
            VALUES (:id, :cid, :lang, :filename, :mime, :size, :pages, :text, :masked, 'uploaded', 'extracted')
            """
        ),
        {"id": analysis_id, "cid": client_id, "lang": lang, "filename": filename, "mime": mime, "size": len(data),
         "pages": extracted.page_count, "text": masked, "masked": masked_count},
    )
    await session.commit()

    try:
        intake = await run_intake(segment_document(masked), filename, lang)
    except Exception as e:
        log.exception("서류 파악 실패 %s", analysis_id)
        await session.execute(text("DELETE FROM analyses WHERE id = :id"), {"id": analysis_id})
        await session.commit()
        raise AnalysisLLMError(t("analysis_failed", lang)) from e
    facts = fx.initial_facts([f.model_dump() for f in intake.facts])
    await session.execute(
        text(
            "UPDATE analyses SET status = 'questions', intake = CAST(:intake AS jsonb), facts = CAST(:facts AS jsonb), "
            "updated_at = now() WHERE id = :id AND status = 'uploaded'"
        ),
        {"id": analysis_id, "intake": intake.model_dump_json(), "facts": json.dumps(facts, ensure_ascii=False)},
    )
    await session.commit()
    return await get_analysis(session, client_id, str(analysis_id))


async def submit_answers(session: AsyncSession, client_id: str, analysis_id: str, answers: list[dict]) -> dict:
    """필수 질문에 모두 답하면 분석을 시작한다. 분석 실패 건은 같은 답변으로 다시 시도할 수 있다."""
    r = await _row(session, client_id, analysis_id, lock=True)
    if r.status not in ("questions", "failed"):
        raise AnalysisStateError(f"Cannot start the analysis in status '{r.status}'.")
    if r.status == "failed" and not answers:
        answers = r.answers or []
    required = [q["id"] for q in (r.intake or {}).get("questions", [])]
    answered = {a["question_id"] for a in answers if a.get("option_id") or (a.get("text") or "").strip()}
    missing = [q for q in required if q not in answered]
    if missing:
        raise MissingAnswers("Please answer all questions — the analysis is tailored to your answers.", missing)
    job_id = uuid.uuid4().hex
    await session.execute(
        text(
            "UPDATE analyses SET answers = CAST(:a AS jsonb), status = 'analyzing', stage = 'extracted', "
            "job_id = :job, error = NULL, result = NULL, checklist = NULL, updated_at = now() WHERE id = :id"
        ),
        {"id": r.id, "a": json.dumps(answers, ensure_ascii=False), "job": job_id},
    )
    await session.commit()
    task = asyncio.create_task(_run(str(r.id), job_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return await get_analysis(session, client_id, analysis_id)


async def set_checklist(session: AsyncSession, client_id: str, analysis_id: str, index: int, done: bool) -> dict:
    """다음 행동 체크. 모두 체크하면 done, 하나라도 풀면 review."""
    r = await _row(session, client_id, analysis_id, lock=True)
    if r.status not in ("review", "done"):
        raise AnalysisStateError(f"The checklist cannot be changed in status '{r.status}'.")
    checklist = list(r.checklist or [])
    if not 0 <= index < len(checklist):
        raise AnalysisError("No such checklist item.")
    checklist[index] = {**checklist[index], "done": bool(done)}
    status = "done" if all(c["done"] for c in checklist) else "review"
    await session.execute(
        text("UPDATE analyses SET checklist = CAST(:c AS jsonb), status = :s, updated_at = now() WHERE id = :id"),
        {"id": r.id, "c": json.dumps(checklist, ensure_ascii=False), "s": status},
    )
    await session.commit()
    return await get_analysis(session, client_id, analysis_id)


async def cancel_analysis(session: AsyncSession, client_id: str, analysis_id: str) -> dict:
    """진행 중인 건을 취소한다. job_id를 지워 이후 도착한 분석 결과가 저장되지 않게 한다."""
    r = await _row(session, client_id, analysis_id, lock=True)
    if r.status not in ACTIVE:
        raise AnalysisStateError(f"Cannot cancel an analysis in status '{r.status}'.")
    await session.execute(
        text("UPDATE analyses SET status = 'canceled', job_id = NULL, stage = NULL, updated_at = now() WHERE id = :id"),
        {"id": r.id},
    )
    await session.commit()
    return await get_analysis(session, client_id, analysis_id)


async def _guarded(session: AsyncSession, analysis_id: str, job_id: str, sets: str, params: dict) -> bool:
    """현재 작업(job_id)이 그대로이고 분석중일 때만 바꾼다. 취소·재시도된 작업이면 False."""
    res = await session.execute(
        text(f"UPDATE analyses SET {sets}, updated_at = now() "
             "WHERE id = :id AND job_id = :job AND status = 'analyzing'"),
        {"id": uuid.UUID(analysis_id), "job": job_id, **params},
    )
    await session.commit()
    return res.rowcount > 0


async def _run(analysis_id: str, job_id: str) -> None:
    async with SessionLocal() as session:
        try:
            with llm.track_usage() as usage:
                result = await _analyze(session, analysis_id, job_id)
            await llm.record_usage(session, "analysis", analysis_id, usage)
            if result is None:
                return
            checklist = [{"index": i, "done": False} for i in range(len(result.get("next_actions") or []))]
            saved = await _guarded(
                session, analysis_id, job_id,
                "status = 'review', stage = 'done', result = CAST(:result AS jsonb), checklist = CAST(:c AS jsonb)",
                {"result": json.dumps(result, ensure_ascii=False), "c": json.dumps(checklist)},
            )
            if not saved:
                log.info("취소·재시도된 분석 결과를 버림 %s (job %s)", analysis_id, job_id)
        except Exception:
            log.exception("서류 분석 실패 %s", analysis_id)
            row = (await session.execute(text("SELECT lang FROM analyses WHERE id = :id"),
                                         {"id": uuid.UUID(analysis_id)})).first()
            lang = row.lang if row else "vi"
            await _guarded(session, analysis_id, job_id, "status = 'failed', stage = NULL, error = :err",
                           {"err": t("analysis_failed", lang)})


async def _analyze(session: AsyncSession, analysis_id: str, job_id: str) -> dict | None:
    r = (await session.execute(text("SELECT * FROM analyses WHERE id = :id"), {"id": uuid.UUID(analysis_id)})).first()
    if r is None or r.job_id != job_id:
        return None
    lang: Lang = r.lang
    intake = Intake.model_validate({"facts": [], **(r.intake or {})})
    answers = r.answers or []
    as_of = today_kr()  # 체류 법령은 지금 시행 중인 것으로 판단한다
    claims = [{k: f[k] for k in ("key", "label", "value")} for f in _doc_facts(r.intake or {})]
    confirmed = [{k: f[k] for k in ("key", "label", "value", "source")} for f in (r.facts or []) if f["confirmed"]]

    segments = segment_document(r.text)
    if not await _guarded(session, analysis_id, job_id, "stage = 'searching'", {}):
        return None
    queries = intake.search_queries_ko or [intake.summary]
    original = f"{intake.doc_type_label}. {intake.summary}"
    law = await retrieve(session, queries, original, as_of, None, include_samples=get_settings().include_samples)

    if not await _guarded(session, analysis_id, job_id, "stage = 'analyzing'", {}):
        return None
    analysis = await run_analysis(segments, intake, answers, law, lang, as_of,
                                  document_claims=claims, confirmed_facts=confirmed)

    if not await _guarded(session, analysis_id, job_id, "stage = 'verifying'", {}):
        return None
    failures = await _citation_failures(session, analysis, as_of)
    if failures:
        log.info("서류 분석 인용 %d건 검증 실패 → 제외", len(failures))
    result = await _build_result(session, intake, analysis, segments, law, lang, as_of)
    return result | {"document_claims": claims, "confirmed_facts": confirmed, "page_count": r.page_count}


def _all_citations(a: DocumentAnalysis) -> list[Citation]:
    return [c for x in a.clauses for c in x.citations] + [c for x in a.cautions for c in x.citations]


async def _citation_failures(session: AsyncSession, a: DocumentAnalysis, as_of) -> list[str]:
    cits = _all_citations(a)
    infos = await lookup(session, [c.provision_id for c in cits], as_of)
    out = []
    for c in cits:
        chk = check_citation(c.provision_id, c.quote_ko, infos.get(c.provision_id))
        if not chk.ok:
            out.append(f"- {c.provision_id}: {chk.reason}")
    return out


async def _build_result(session, intake: Intake, a: DocumentAnalysis, segments: list[Segment], law, lang: Lang, as_of):
    cits = _all_citations(a)
    infos = await lookup(session, [c.provision_id for c in cits], as_of)
    paths = dict(
        (await session.execute(
            text("SELECT id, path FROM provisions WHERE id = ANY(:ids)"),
            {"ids": list({c.provision_id for c in cits} | {(infos[c.provision_id].jo_id or "") for c in cits
                                                           if c.provision_id in infos})},
        )).all()
    ) if cits else {}

    def cite(c: Citation) -> dict | None:
        chk = check_citation(c.provision_id, c.quote_ko, infos.get(c.provision_id))
        if not chk.ok:
            return None  # 재생성 후에도 검증에 실패한 인용은 보여주지 않는다
        pid = chk.corrected_id or c.provision_id
        return {"provision_id": pid, "path": paths.get(pid, pid), "quote_ko": c.quote_ko,
                "quote_translation": c.quote_translation}

    seg_by_id = {s.id: s for s in segments}
    seen: set[str] = set()
    clauses = []
    for f in a.clauses:
        seg = seg_by_id.get(f.clause_id)
        if not seg or f.clause_id in seen:
            continue
        seen.add(f.clause_id)
        clauses.append({
            "id": f.clause_id,
            "title": f.title,
            "category": f.category,
            "explanation": f.explanation_detail,
            "explanation_simple": f.explanation_simple,
            "explanation_detail": f.explanation_detail,
            "highlights": [h for h in f.highlights if h.strip() and quote_in_text(h, seg.text)],
            "text": seg.text,
            "pages": seg.pages,
            "citations": [x for x in map(cite, f.citations) if x],
        })
    for seg in segments:  # 모델이 언급하지 않은 조항은 일반 조항으로 둔다
        if seg.id not in seen:
            clauses.append({"id": seg.id, "title": seg.title, "category": "general", "explanation": None,
                            "explanation_simple": None, "explanation_detail": None,
                            "highlights": [], "text": seg.text, "pages": seg.pages, "citations": []})
    order = {s.id: i for i, s in enumerate(segments)}
    clauses.sort(key=lambda c: order.get(c["id"], 0))

    counts = {k: sum(c["category"] == k for c in clauses) for k in ("must_check", "caution", "general")}
    # 꼭 확인할 조항 대부분에 검증된 근거가 없으면 신뢰도를 낮춘다
    must = [c for c in clauses if c["category"] == "must_check"]
    uncited = sum(not c["citations"] for c in must)
    confidence = "low" if must and uncited * 2 > len(must) else a.confidence
    return {
        "title": intake.title,
        "doc_type_label": intake.doc_type_label,
        "doc_kind": intake.doc_kind,
        "summary": a.summary,
        "summary_simple": a.summary_simple,
        "situation_note": a.situation_note,
        "basic_info": [i.model_dump() for i in intake.basic_info],
        "counts": counts,
        "clauses": clauses,
        "cautions": [
            {"title": c.title, "detail": c.explanation_detail, "explanation": c.explanation_detail,
             "explanation_simple": c.explanation_simple, "explanation_detail": c.explanation_detail, "kind": c.kind,
             "clause_ids": [x for x in c.clause_ids if x in seg_by_id],
             "citations": [x for x in map(cite, c.citations) if x]}
            for c in a.cautions
        ],
        "next_actions": [
            {"id": f"a{i + 1}", "text": x.text, "clause_id": x.clause_id if x.clause_id in seg_by_id else None,
             "due": x.due}
            for i, x in enumerate(a.next_actions)
        ],
        "open_questions": [{"id": f"oq{i + 1}", "question": q.question, "why": q.why}
                           for i, q in enumerate(a.open_questions[:3])],
        "confidence": confidence,
        "needs_expert": a.needs_expert or confidence == "low",
        "notice": t("low_confidence", lang) if confidence == "low" else None,
        "not_immigration": intake.doc_kind == "not_immigration",
        "disclaimer": t("disclaimer", lang),
        "as_of": as_of.isoformat(),
        "law_sources": [{"provision_id": i.provision_id, "path": i.path} for i in law],
    }
