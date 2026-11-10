"""질의응답 오케스트레이션. 단계 이벤트를 흘려보내므로 SSE와 일반 JSON 응답 모두에 쓴다."""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import llm
from app.core.config import get_settings
from app.core.lang import DEFAULT_LANG, Lang, t
from app.generation.answer import LegalAnswer, generate_answer
from app.generation.citations import align_citations
from app.generation.numbers import check_numbers
from app.generation.verify import ProvisionInfo, check_citation, lookup
from app.retrieval.pipeline import ContextItem, retrieve
from app.retrieval.rewrite import resolve_as_of, rewrite_query
from app.schemas.chat import AnswerPayload, ChatRequest, CitationOut, NumberCheckOut, SourceOut, UsageOut

log = logging.getLogger(__name__)


def _question(original: str, standalone: str) -> str:
    """원래 질문을 그대로 쓰고, 대화 맥락으로 풀어 쓴 질문은 참고로 덧붙인다 (답변 언어가 흔들리지 않게)"""
    return original if standalone.strip() == original.strip() else f"{original}\n(Context: {standalone})"


def _stage(name: str, lang: Lang) -> dict:
    return {"event": "stage", "data": {"stage": name, "label": t(f"stage.{name}", lang)}}


async def answer_stream(
    session: AsyncSession, req: ChatRequest, analysis: "AnalysisContext | None" = None
) -> AsyncIterator[dict]:
    """analysis를 미리 불러 넘기면 그대로 쓰고, 없으면 req.analysis_id로 찾는다 (없는 ID면 무시)."""
    if req.session_id:
        # 같은 세션에 새 메시지가 왔으면 사용자가 앞선 후속 질문에 답한 것으로 본다
        await resolve_session_questions(session, req.session_id)
    if analysis is None and req.analysis_id:
        analysis = await load_analysis_context(session, req.analysis_id, req.client_id)
        if analysis is None:
            log.warning("분석 %s를 찾지 못해 문서 맥락 없이 답변", req.analysis_id)
    with llm.track_usage() as usage:
        async for ev in _answer_stream(session, req, analysis, usage):
            yield ev


async def _answer_stream(
    session: AsyncSession, req: ChatRequest, analysis: "AnalysisContext | None", usage: llm.Usage
) -> AsyncIterator[dict]:
    lang: Lang = req.lang or DEFAULT_LANG
    history = [m.model_dump() for m in req.history]
    settings = get_settings()
    document = analysis.block if analysis else None

    t0 = time.perf_counter()
    yield _stage("rewriting", lang)
    # 문서 후속 질문은 "이 벌금"처럼 문서를 가리키므로, 질의 재작성에 문서 요약을 대화 맥락으로 준다
    rewrite_history = [{"role": "assistant", "content": analysis.brief}, *history] if analysis else history
    rq = await rewrite_query(req.message, lang, rewrite_history)
    t_rewrite = time.perf_counter()
    # 기준일: 요청 as_of > 질문에 적힌 날짜 > 분석 당시 기준일 > 오늘
    as_of = resolve_as_of(rq, req.as_of or (None if rq.as_of or not analysis else analysis.as_of))

    yield _stage("searching", lang)
    stages: list[str] = []

    async def on_stage(name: str) -> None:
        stages.append(name)

    queries = list(dict.fromkeys([*rq.queries_ko, *(analysis.search_queries[:1] if analysis else [])]))
    items = await retrieve(
        session,
        queries,
        rq.standalone_question,
        as_of,
        None,  # 코퍼스가 교통 법령뿐이라 분야 필터는 쓰지 않는다
        include_samples=settings.include_samples,
        on_stage=on_stage,
    )
    for name in stages:
        yield _stage(name, lang)

    if not items:
        payload = _empty(lang, as_of, rq.queries_ko)
        payload.analysis_id = analysis.id if analysis else None
        await _finish(session, req, analysis, payload, usage)
        yield {"event": "answer", "data": payload.model_dump(mode="json")}
        return

    t_search = time.perf_counter()
    yield _stage("generating", lang)
    # 답변 문장을 생성되는 대로 흘려보낸다 (delta 이벤트). 생성 작업은 별도 태스크로 돌리고 큐로 받는다
    queue: asyncio.Queue = asyncio.Queue()

    async def on_text(text: str) -> None:
        await queue.put({"event": "delta", "data": {"text": text}})

    task = asyncio.create_task(generate_answer(
        _question(req.message, rq.standalone_question), items, lang, as_of, history, on_text=on_text, document=document
    ))
    while not task.done() or not queue.empty():
        try:
            yield await asyncio.wait_for(queue.get(), timeout=0.25)
        except TimeoutError:
            continue
    ans = task.result()

    yield _stage("verifying", lang)
    ans, checks, infos = await _verify(session, ans, as_of)
    failed = [c for c in checks if not c.ok]
    # 인용 절반 이상이 틀렸을 때만 다시 생성한다 (재생성은 응답 시간을 두 배로 늘린다)
    if failed and len(failed) * 2 >= len(checks):
        log.info("인용 검증 실패 %d건, 재생성", len(failed))
        feedback = (
            "Internal check (do not mention it to the user): some citations in your draft were invalid:\n"
            + "\n".join(f"- {c.provision_id}: {c.reason}" for c in failed)
            + "\nWrite the complete answer to the user's question again from scratch, citing only provided provisions "
            "with verbatim quotes. The user must not see any reference to this correction."
        )
        yield {"event": "reset", "data": {}}
        ans = await generate_answer(
            _question(req.message, rq.standalone_question), items, lang, as_of, history, feedback=feedback,
            document=document,
        )
        ans, checks, infos = await _verify(session, ans, as_of)

    log.info(
        "chat timing rewrite=%.1fs search=%.1fs generate+verify=%.1fs retried=%s",
        t_rewrite - t0, t_search - t_rewrite, time.perf_counter() - t_search, bool(failed and len(failed) * 2 >= len(checks)),
    )
    # 본문 [n]과 인용 목록을 marker로 짝짓고 본문에 나온 순서대로 다시 번호를 매긴다 (본문에서 안 쓴 인용은 버림)
    ans.answer, pairs = align_citations(ans.answer, [(c.marker, (c, chk)) for c, chk in zip(ans.citations, checks)])
    # 재생성 후에도 실패한 인용은 verified=false로 남겨 앱에서 경고를 보이고, 신뢰도를 낮춘다
    bad = sum(not chk.ok for _, chk in pairs)
    if bad and bad * 3 > len(pairs):
        ans.confidence = "low"
    elif bad and ans.confidence == "high":
        ans.confidence = "medium"

    # 답변 속 금액·기간·벌점 숫자가 인용·검색된 조문 원문에 있는지 확인하고, 없으면 신뢰도를 한 단계 낮춘다
    number_checks = check_numbers(ans.answer, _number_sources(ans, infos, items, analysis))
    missing = [c for c in number_checks if c.status == "not_found"]
    log.info("number checks verified=%d not_found=%d %s", len(number_checks) - len(missing), len(missing),
             [c.text for c in missing])
    if missing:
        ans.confidence = {"high": "medium", "medium": "low"}.get(ans.confidence, "low")

    context_by_id = {i.provision_id: i for i in items}
    payload = AnswerPayload(
        lang=lang,
        as_of=as_of,
        answer=ans.answer,
        citations=[
            CitationOut(
                index=n + 1,
                provision_id=chk.corrected_id or c.provision_id,
                quote_ko=c.quote_ko,
                quote_translation=c.quote_translation,
                verified=chk.ok,
                verify_error=chk.reason,
            )
            for n, (c, chk) in enumerate(pairs)
        ],
        confidence=ans.confidence,
        needs_expert=ans.needs_expert or ans.confidence == "low",
        follow_up_questions=ans.follow_up_questions,
        notice=t("low_confidence", lang) if ans.confidence == "low" else None,
        disclaimer=t("disclaimer", lang),
        sources=[
            SourceOut(
                provision_id=i.provision_id,
                document_id=i.document_id,
                title=i.title_ko,
                path=i.path,
                retrieved_by=i.source,
            )
            for i in context_by_id.values()
        ],
        search_queries=rq.queries_ko,
        number_checks=[NumberCheckOut(**c.as_dict()) for c in number_checks],
        analysis_id=analysis.id if analysis else None,
    )
    await _finish(session, req, analysis, payload, usage)
    yield {"event": "answer", "data": payload.model_dump(mode="json")}


async def _finish(
    session: AsyncSession, req: ChatRequest, analysis: "AnalysisContext | None", payload: AnswerPayload,
    usage: llm.Usage,
) -> None:
    """answer 이벤트 직전: 사용량 기록, 미해결 질문 저장."""
    payload.usage = UsageOut(**usage.as_dict())
    log.info("chat usage %s by_model=%s", payload.usage, usage.by_model)
    ref = str(analysis.id) if analysis else req.session_id
    await llm.record_usage(session, "chat", ref, usage)
    questions = [q for q in payload.follow_up_questions if q.strip()]
    if not questions and payload.confidence == "low":
        questions = [req.message]  # 답하지 못한 질문 자체를 남긴다
    if questions and (req.session_id or analysis):
        await store_open_questions(
            session, questions, session_id=req.session_id, analysis_id=analysis.id if analysis else None,
            source="analysis" if analysis else "chat",
        )


def _number_sources(
    ans: LegalAnswer, infos: dict[str, ProvisionInfo], items: list[ContextItem], analysis: "AnalysisContext | None"
) -> list[tuple[str, str]]:
    """숫자 확인에 쓸 원문: 인용한 조문(항·조 전체) → 검색된 조문 → 분석 문서 조항 순."""
    out: list[tuple[str, str]] = []
    for c in ans.citations:
        info = infos.get(c.provision_id)
        if info:
            out.append((info.id, info.full_text))
            if info.jo_id and info.jo_id != info.id:
                out.append((info.jo_id, info.jo_full_text))
    out.extend((i.provision_id, i.text_ko) for i in items)
    if analysis:
        out.extend(analysis.sources)
    return out


async def _verify(session: AsyncSession, ans: LegalAnswer, as_of: date):
    infos = await lookup(session, [c.provision_id for c in ans.citations], as_of)
    checks = [check_citation(c.provision_id, c.quote_ko, infos.get(c.provision_id)) for c in ans.citations]
    return ans, checks, infos


def _empty(lang: Lang, as_of: date, queries: list[str]) -> AnswerPayload:
    return AnswerPayload(
        lang=lang,
        as_of=as_of,
        answer=t("no_results", lang),
        citations=[],
        confidence="low",
        needs_expert=False,
        follow_up_questions=[],
        notice=None,
        disclaimer=t("disclaimer", lang),
        sources=[],
        search_queries=queries,
    )


# ---------------------------------------------------------------------------
# 분석한 문서에 대한 후속 질문
# ---------------------------------------------------------------------------

DOC_CLAUSE_CHARS = 6000  # 프롬프트에 넣을 조항 원문 총 길이
_CATEGORY_ORDER = {"must_check": 0, "caution": 1, "general": 2}


@dataclass
class AnalysisContext:
    id: UUID
    block: str                      # <analysed_document> 안에 넣을 본문
    brief: str                      # 질의 재작성용 한 줄 요약
    as_of: date | None
    search_queries: list[str] = field(default_factory=list)
    sources: list[tuple[str, str]] = field(default_factory=list)  # 숫자 확인용 (document:C3, 조항 원문)


def _as_dict(v) -> dict:
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return {}
    return v if isinstance(v, dict) else {}


def _fact_lines(items) -> list[str]:
    """confirmed_facts / document_claims / facts 는 다른 작업에서 형식이 바뀔 수 있어 문자열·dict 모두 받는다."""
    if isinstance(items, dict):
        items = [f"{k}: {v}" for k, v in items.items()]
    out = []
    for x in items or []:
        if isinstance(x, dict):
            label = x.get("label") or x.get("key") or x.get("title") or ""
            value = x.get("value") or x.get("text") or x.get("detail") or x.get("claim") or ""
            line = f"{label}: {value}" if label and value else str(label or value or "")
        else:
            line = str(x)
        if line.strip():
            out.append(f"- {line.strip()}")
    return out


def build_analysis_context(analysis_id: UUID, intake, answers, result) -> AnalysisContext:
    """analyses 행에서 답변 생성용 문서 맥락을 만든다 (순수 함수)."""
    intake, result = _as_dict(intake), _as_dict(result)
    title = result.get("title") or intake.get("title") or "Uploaded document"
    doc_type = result.get("doc_type_label") or intake.get("doc_type_label") or ""
    summary = result.get("summary") or intake.get("summary") or ""
    lines = [f"Title: {title}", f"Type: {doc_type}" if doc_type else "", f"Summary: {summary}" if summary else ""]
    if result.get("situation_note"):
        lines.append(f"User situation: {result['situation_note']}")

    info = _fact_lines(result.get("basic_info") or intake.get("basic_info"))
    if info:
        lines += ["Key facts in the document:", *info]
    # 사용자가 분석 전에 답한 질문 (질문 문구와 선택지를 이어 붙인다)
    qs = {q.get("id"): q for q in intake.get("questions") or [] if isinstance(q, dict)}
    answered = []
    for a in answers if isinstance(answers, list) else []:
        if not isinstance(a, dict):
            continue
        q = qs.get(a.get("question_id")) or {}
        opt = next((o.get("label") for o in q.get("options") or [] if o.get("id") == a.get("option_id")), None)
        reply = " / ".join(x for x in (opt, (a.get("text") or "").strip()) if x)
        if q.get("text") and reply:
            answered.append(f"- {q['text']} → {reply}")
    if answered:
        lines += ["User's answers:", *answered]
    for key, label in (("confirmed_facts", "Confirmed facts"), ("facts", "Facts"),
                       ("document_claims", "What the document claims")):
        facts = _fact_lines(result.get(key))
        if facts:
            lines += [f"{label}:", *facts]
    cautions = [c for c in result.get("cautions") or [] if isinstance(c, dict)]
    if cautions:
        lines += ["Cautions found:", *(f"- {c.get('title', '')}: {c.get('detail', '')}" for c in cautions[:6])]

    clauses = [c for c in result.get("clauses") or [] if isinstance(c, dict)]
    clauses.sort(key=lambda c: _CATEGORY_ORDER.get(c.get("category"), 3))
    budget = DOC_CLAUSE_CHARS
    clause_blocks, sources = [], []
    for c in clauses:
        body = (c.get("text") or "").strip()
        if c.get("text"):
            sources.append((f"document:{c.get('id')}", c["text"]))
        if budget <= 0 and c.get("category") == "general":
            continue
        head = f"[{c.get('id')}] {c.get('title') or ''} ({c.get('category')})"
        if c.get("explanation"):
            head += f"\n  Analysis: {c['explanation']}"
        snippet = body[:budget] + ("…" if len(body) > budget else "") if budget > 0 else ""
        budget -= len(snippet)
        clause_blocks.append(f"{head}\n{snippet}" if snippet else head)
    if clause_blocks:
        lines += ["Clauses:", *clause_blocks]

    as_of = None
    if result.get("as_of"):
        try:
            as_of = date.fromisoformat(str(result["as_of"])[:10])
        except ValueError:
            as_of = None
    return AnalysisContext(
        id=analysis_id,
        block="\n".join(x for x in lines if x),
        brief=f"(The user uploaded a document for analysis: {title}{f' — {doc_type}' if doc_type else ''}. {summary})",
        as_of=as_of,
        search_queries=[q for q in intake.get("search_queries_ko") or [] if isinstance(q, str)],
        sources=sources,
    )


async def load_analysis_context(
    session: AsyncSession, analysis_id: UUID | str, client_id: str | None = None
) -> AnalysisContext | None:
    """분석 결과가 나온(review·done) 본인 건만 문서 맥락으로 쓴다."""
    try:
        aid = analysis_id if isinstance(analysis_id, UUID) else UUID(str(analysis_id))
    except ValueError:
        return None
    row = (await session.execute(
        text(
            "SELECT id, intake, answers, result FROM analyses WHERE id = :id "
            "AND client_id = :cid AND status IN ('review', 'done') AND result IS NOT NULL"
        ),
        {"id": aid, "cid": client_id},
    )).first()
    if row is None:
        return None
    return build_analysis_context(row.id, row.intake, row.answers, row.result)


# ---------------------------------------------------------------------------
# 미해결 질문 (open_questions)
# ---------------------------------------------------------------------------


async def store_open_questions(
    session: AsyncSession, questions: list[str], *, session_id: str | None, analysis_id: UUID | None, source: str
) -> None:
    try:
        await session.execute(
            text(
                "INSERT INTO open_questions (session_id, analysis_id, source, question) "
                "VALUES (:sid, :aid, :source, :q)"
            ),
            [{"sid": session_id, "aid": analysis_id, "source": source, "q": q} for q in questions if q.strip()],
        )
        await session.commit()
    except Exception:
        log.exception("open_questions 저장 실패")
        await session.rollback()


async def resolve_session_questions(session: AsyncSession, session_id: str) -> None:
    try:
        await session.execute(
            text(
                "UPDATE open_questions SET resolved = true, resolved_at = now() "
                "WHERE session_id = :sid AND NOT resolved"
            ),
            {"sid": session_id},
        )
        await session.commit()
    except Exception:
        log.exception("open_questions 해결 처리 실패")
        await session.rollback()
