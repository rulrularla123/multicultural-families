"""법령 번역 피드백: LLM 번역 금지, NMT 요청 경계·장애·캐시·실제 API 라우트 확인."""

import asyncio
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app import translation
from app.core.config import Settings
from app.core.db import get_session
from app.documents.analyze import DocumentAnalysis
from app.documents.segment import Segment
from app.generation.answer import AnswerCitation, LegalAnswer
from app.generation.verify import ProvisionInfo
from app.main import app
from app.retrieval.pipeline import ContextItem
from app.services import documents, qa

QUOTE = "외국인은 체류기간이 끝나기 전에 체류기간 연장허가를 받아야 한다."
OTHER = "체류지를 변경한 경우 신고하여야 한다."
VI = "Người nước ngoài phải được phép gia hạn trước khi hết thời hạn lưu trú."
PID = "출입국관리법:J25"


@pytest.fixture(autouse=True)
def translation_settings(monkeypatch):
    settings = Settings(_env_file=None, llm_fake=False, azure_translator_key="test-only-key")
    monkeypatch.setattr(translation, "get_settings", lambda: settings)
    translation._cache.clear()
    yield settings
    translation._cache.clear()


def mock_api(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(translation.httpx, "AsyncClient", lambda **kw: client(
        transport=httpx.MockTransport(handler), **kw
    ))


def test_nmt_wire_request_deduplicates_and_caches_by_exact_source(monkeypatch):
    sent = []

    def respond(request):
        body = json.loads(request.content)
        sent.append(body)
        assert str(request.url).split("?")[0] == translation.ENDPOINT
        assert request.headers["Ocp-Apim-Subscription-Key"] == "test-only-key"
        assert "Ocp-Apim-Subscription-Region" not in request.headers
        assert dict(request.url.params) == {
            "api-version": "3.0", "from": "ko", "to": "vi", "textType": "plain", "category": "general"
        }
        return httpx.Response(200, json=[{"translations": [{"text": "A & B", "to": "vi"}]} for _ in body])

    mock_api(monkeypatch, respond)
    first = asyncio.run(translation.translate_texts([QUOTE, QUOTE], "vi"))
    assert first == [translation.Translation("A & B", "translated", "azure_translator")] * 2
    asyncio.run(translation.translate_texts([QUOTE], "vi"))
    asyncio.run(translation.translate_texts([QUOTE + " 개정"], "vi"))
    assert sent == [[{"Text": QUOTE}], [{"Text": QUOTE + " 개정"}]]


def test_long_quotation_is_not_truncated(monkeypatch):
    source = (QUOTE + "\n") * 200
    sent = []

    def respond(request):
        parts = [row["Text"] for row in json.loads(request.content)]
        sent.extend(parts)
        return httpx.Response(200, json=[{"translations": [{"text": "đoạn", "to": "vi"}]} for _ in parts])

    mock_api(monkeypatch, respond)
    result = asyncio.run(translation.translate_texts([source], "vi"))[0]
    assert "".join(sent) == source and all(len(p) <= 4500 for p in sent)
    assert result.status == "translated" and len(result.text.splitlines()) == len(sent)


@pytest.mark.parametrize("failure", ["timeout", "401", "quota", "429", "503", "json", "count", "empty", "language", "targets"])
def test_failure_never_returns_or_caches_a_translation(monkeypatch, failure, caplog):
    def respond(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("test-only-key private-error", request=request)
        if failure in ("401", "429", "503"):
            return httpx.Response(int(failure), text="test-only-key private-error")
        if failure == "quota":
            return httpx.Response(403, json={"error": {"code": 403001, "message": "Free quota exceeded"}})
        if failure == "json":
            return httpx.Response(200, text="bad json")
        targets = [{"text": "" if failure == "empty" else VI, "to": "en" if failure == "language" else "vi"}]
        rows = [] if failure == "count" else [{"translations": [] if failure == "targets" else targets}]
        return httpx.Response(200, json=rows)

    mock_api(monkeypatch, respond)
    assert asyncio.run(translation.translate_texts([QUOTE], "vi")) == [translation.Translation()]
    assert not translation._cache
    assert "test-only-key" not in caplog.text and "private-error" not in caplog.text


def test_regional_resource_sends_region_header(monkeypatch, translation_settings):
    translation_settings.azure_translator_region = "koreacentral"

    def respond(request):
        assert request.headers["Ocp-Apim-Subscription-Region"] == "koreacentral"
        assert request.headers["Ocp-Apim-Subscription-Key"] == "test-only-key"
        return httpx.Response(200, json=[{"translations": [{"text": VI, "to": "vi"}]}])

    mock_api(monkeypatch, respond)
    assert asyncio.run(translation.translate_texts([QUOTE], "vi"))[0].text == VI


def test_korean_missing_key_and_development_never_call_api(monkeypatch, translation_settings):
    def forbidden(**kw):
        pytest.fail("번역 API를 호출하면 안 됨")

    monkeypatch.setattr(translation.httpx, "AsyncClient", forbidden)
    assert asyncio.run(translation.translate_texts([QUOTE], "ko"))[0].text == QUOTE
    translation_settings.azure_translator_key = ""
    assert asyncio.run(translation.translate_texts([QUOTE], "vi"))[0].status == "unavailable"
    translation_settings.llm_fake = True
    fake = asyncio.run(translation.translate_texts([QUOTE], "vi"))[0]
    assert fake.status == "development" and fake.text.startswith("[DEV FAKE TRANSLATION]")


def test_llm_response_schemas_do_not_request_translation():
    assert "quote_translation" not in json.dumps(LegalAnswer.model_json_schema())
    assert "quote_translation" not in json.dumps(DocumentAnalysis.model_json_schema())


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("available", [False, True])
def test_chat_routes_translate_only_verified_citations(monkeypatch, stream, available):
    """US-01: 실제 앱의 JSON·SSE 라우트에서 검증된 법령만 NMT에 전달한다."""
    sent = []

    def respond(request):
        sent.extend(row["Text"] for row in json.loads(request.content))
        return httpx.Response(200 if available else 503, json=[{"translations": [{"text": VI, "to": "vi"}]}])

    mock_api(monkeypatch, respond)
    citations = [AnswerCitation(provision_id=PID, quote_ko=q, marker=i + 1)
                 for i, q in enumerate([QUOTE, OTHER, "원문에 없는 문장"])]
    answer = LegalAnswer(answer="Hướng dẫn [1][2][3].", citations=citations, confidence="high",
                         needs_expert=False, follow_up_questions=[])
    monkeypatch.setattr(qa, "rewrite_query", AsyncMock(return_value=SimpleNamespace(
        intent="legal", queries_ko=["체류기간 연장"], standalone_question="체류기간 연장", as_of=None
    )))
    monkeypatch.setattr(qa, "retrieve", AsyncMock(return_value=[ContextItem(
        PID, "출입국관리법", "출입국관리법", None, "law", "제25조", QUOTE + OTHER,
        None, None, "in_force", 1.0, "search"
    )]))
    monkeypatch.setattr(qa, "generate_answer", AsyncMock(return_value=answer))
    monkeypatch.setattr(qa, "lookup", AsyncMock(return_value={
        PID: ProvisionInfo(PID, QUOTE + OTHER, PID, QUOTE + OTHER, True)
    }))
    monkeypatch.setattr(qa.llm, "record_usage", AsyncMock())

    async def no_db():
        yield None

    app.dependency_overrides[get_session] = no_db
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/chat" + ("/stream" if stream else ""), json={
                "message": "개인 질문은 번역 API에 보내지 않는다", "lang": "vi"
            })
        assert response.status_code == 200, response.text
        body = json.loads(response.text.split("event: answer\ndata: ")[1].split("\n\n")[0]) if stream else response.json()
        assert set(sent) == {QUOTE, OTHER}
        for c in body["citations"][:2]:
            assert c["quote_translation"] == (VI if available else "")
            assert c["translation_status"] == ("translated" if available else "unavailable")
            assert c["verified"] is True
        assert body["citations"][2]["quote_translation"] == ""
        assert body["citations"][2]["translation_status"] == "not_verified"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_document_analysis_translates_valid_quotes_and_deduplicates_cautions(monkeypatch):
    """US-04: 서류 원문·답변은 보내지 않고, 조항·주의점의 검증된 인용만 번역한다."""
    sent = []

    def respond(request):
        sent.extend(row["Text"] for row in json.loads(request.content))
        return httpx.Response(200, json=[{"translations": [{"text": VI, "to": "vi"}]}])

    mock_api(monkeypatch, respond)
    monkeypatch.setattr(documents, "lookup", AsyncMock(return_value={
        PID: ProvisionInfo(PID, QUOTE, PID, QUOTE, True)
    }))
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))
    citation = {"provision_id": PID, "quote_ko": QUOTE}
    analysis = DocumentAnalysis(
        summary="summary", summary_simple="simple", situation_note="note", next_actions=[], open_questions=[],
        confidence="high", needs_expert=False,
        clauses=[{"clause_id": "C1", "title": "clause", "category": "must_check", "explanation_simple": "simple",
                  "explanation_detail": "detail", "highlights": [],
                  "citations": [citation, {"provision_id": PID, "quote_ko": "없는 문장"}]}],
        cautions=[{"title": "caution", "explanation_simple": "simple", "explanation_detail": "detail",
                   "kind": "deadline", "clause_ids": ["C1"], "citations": [citation]}],
    )
    intake = SimpleNamespace(title="private title", doc_type_label="notice", doc_kind="immigration_notice", basic_info=[])
    result = asyncio.run(documents._build_result(
        session, intake, analysis, [Segment("C1", "title", "개인 서류 본문")], [], "vi", date.today()
    ))
    assert sent == [QUOTE]
    assert len(result["clauses"][0]["citations"]) == 1
    assert result["clauses"][0]["citations"][0]["quote_translation"] == VI
    assert result["cautions"][0]["citations"][0]["translation_provider"] == "azure_translator"


def test_legacy_document_translation_is_hidden_without_mutating_saved_result():
    saved = {"clauses": [{"citations": [{"quote_ko": QUOTE, "quote_translation": "old LLM translation"}]}]}
    public = documents._result_view(saved)
    assert public["clauses"][0]["citations"][0]["quote_translation"] == ""
    assert saved["clauses"][0]["citations"][0]["quote_translation"] == "old LLM translation"


def test_vietnamese_summary_uses_korean_llm_output_then_api(monkeypatch, translation_settings):
    from app.core import config
    from ingest import pipeline

    monkeypatch.setattr(config, "get_settings", lambda: translation_settings)
    complete = AsyncMock(return_value="체류기간이 끝나기 전에 연장허가가 필요하다.")
    monkeypatch.setattr(pipeline, "complete", complete)
    stored = []
    sent = []

    async def execute(statement, params=None):
        sql = str(statement)
        if "SELECT p.id" in sql:
            rows = [SimpleNamespace(id=PID, document_id="출입국관리법", path="제25조", full_text_ko=QUOTE, domains=[])]
        elif "SELECT c.jo_id" in sql:
            rows = [SimpleNamespace(jo_id=PID, document_id="출입국관리법", content=stored[0]["content"], domains=[])]
        else:
            stored.extend(params)
            rows = []
        return SimpleNamespace(all=lambda: rows)

    def respond(request):
        sent.extend(row["Text"] for row in json.loads(request.content))
        return httpx.Response(200, json=[{"translations": [{"text": VI, "to": "vi"}]}])

    mock_api(monkeypatch, respond)
    session = SimpleNamespace(execute=execute, commit=AsyncMock())
    assert asyncio.run(pipeline.summarize_missing(session, "vi")) == 1
    assert complete.await_count == 1
    assert "한국어" in complete.await_args.args[0]
    assert sent == [complete.return_value]
    assert [(c["kind"], c["lang"]) for c in stored] == [("summary", "ko"), ("azure_translated_summary", "vi")]
    assert stored[1]["content"] == f"[제25조]\n{VI}"


def test_summary_missing_key_fails_before_paid_llm_or_database(monkeypatch, translation_settings):
    from app.core import config
    from ingest import pipeline

    translation_settings.azure_translator_key = ""
    monkeypatch.setattr(config, "get_settings", lambda: translation_settings)
    complete = AsyncMock()
    monkeypatch.setattr(pipeline, "complete", complete)
    with pytest.raises(RuntimeError, match="AZURE_TRANSLATOR_KEY"):
        asyncio.run(pipeline.summarize_missing(None, "vi"))
    complete.assert_not_awaited()


@pytest.mark.db
@pytest.mark.parametrize("available", [False, True])
def test_provision_route_and_search_exclude_legacy_summary_in_real_db(monkeypatch, available):
    """US-02: PostgreSQL 적재·실제 앱 조회·검색에서 이전 LLM 요약과 API 번역을 구분한다."""
    from sqlalchemy import delete, insert

    from app.core.db import SessionLocal, engine
    from app.models.law import Chunk, LegalDocument, Provision
    from app.retrieval.bm25 import ROWS_SQL
    from app.retrieval.pipeline import PROVISIONS_SQL
    from ingest.pipeline import translate_summaries_missing

    doc_id, pid = "_translation_contract", "_translation_contract:J1"
    sent = []

    def respond(request):
        sent.extend(row["Text"] for row in json.loads(request.content))
        return httpx.Response(200 if available else 503, json=[{"translations": [{"text": VI, "to": "vi"}]}])

    mock_api(monkeypatch, respond)

    async def seed():
        async with SessionLocal() as session:
            session.add(LegalDocument(id=doc_id, doc_type="law", title_ko="번역 테스트", is_sample=True))
            await session.flush()
            session.add(Provision(id=pid, document_id=doc_id, jo_id=pid, level="jo", number="1", path="제1조",
                                  ordinal=1, text_ko=QUOTE, full_text_ko=QUOTE))
            await session.flush()
            await session.execute(insert(Chunk), [
                {"provision_id": pid, "jo_id": pid, "document_id": doc_id, "kind": "summary", "lang": lang,
                 "content": f"[제1조]\n{body}", "domains": []}
                for lang, body in [("vi", "legacy LLM translation"), ("ko", QUOTE)]
            ])
            await session.commit()

    async def ingest_and_search():
        async with SessionLocal() as session:
            if available:
                assert await translate_summaries_missing(session) == 1
                assert await translate_summaries_missing(session) == 0
            else:
                with pytest.raises(RuntimeError, match="법령 요약 번역 실패"):
                    await translate_summaries_missing(session)
            rows = (await session.execute(ROWS_SQL)).all()
            assert not any("legacy LLM translation" in r.content for r in rows)
            context = (await session.execute(PROVISIONS_SQL, {"ids": [pid]})).one()
            assert context.summary_vi == (f"[제1조]\n{VI}" if available else None)

    async def cleanup():
        async with SessionLocal() as session:
            await session.execute(delete(LegalDocument).where(LegalDocument.id == doc_id))
            await session.commit()

    with TestClient(app) as client:
        try:
            client.portal.call(seed)
            before = client.get("/api/v1/provisions", params={"id": pid})
            assert before.status_code == 200, before.text
            assert before.json()["summary_vi"] is None
            client.portal.call(ingest_and_search)
            after = client.get("/api/v1/provisions", params={"id": pid})
            assert after.status_code == 200, after.text
            body = after.json()
            assert body["summary_vi"] == (VI if available else None)
            assert body["summary_translation_status"] == ("translated" if available else "unavailable")
            assert body["full_text_ko"] == QUOTE
            assert sent == [QUOTE]
        finally:
            client.portal.call(cleanup)
            client.portal.call(engine.dispose)
