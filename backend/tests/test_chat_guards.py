"""US-01: 공백 거절, LLM 전 마스킹, 인용이 없는 법적 주장 공개 방지."""
import asyncio
from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import llm
from app.generation.answer import LegalAnswer
from app.generation.verify import CitationCheck
from app.retrieval.pipeline import ContextItem
from app.retrieval.rewrite import RewrittenQuery
from app.schemas.chat import ChatRequest
from app.services import qa

CLAIM = "이 경우 신고 의무가 없습니다"
PHONE = "010-9876-5432"


def answer(body="조문을 확인하세요 [1].", markers=(1,)):
    return LegalAnswer(answer=body, citations=[{
        "marker": n, "provision_id": "test:J1", "quote_ko": "모의 조문", "quote_translation": "모의 조문",
    } for n in markers], confidence="high", needs_expert=False, follow_up_questions=[])


def events(monkeypatch, answers, req=None, analysis=None):
    seen = []
    generated = []

    async def rewrite(message, lang, history):
        seen.append((message, history))
        return RewrittenQuery(intent="legal", queries_ko=["체류"], domains=[], as_of=None,
                              standalone_question=message)

    async def generate(question, items, lang, as_of, history, **kwargs):
        seen.append((question, history, kwargs.get("document")))
        item = answers[min(len(generated), len(answers) - 1)].model_copy(deep=True)
        generated.append(item)
        if kwargs.get("on_text"):
            await kwargs["on_text"](item.answer)
        return item

    async def verify(session, item, as_of):
        return item, [CitationCheck(c.provision_id, True) for c in item.citations], {}

    context = ContextItem("test:J1", "test", "모의 법령", None, "law", "제1조", "모의 조문", None,
                          date(2000, 1, 1), "in_force", 1.0, "search")
    monkeypatch.setattr(qa, "rewrite_query", rewrite)
    monkeypatch.setattr(qa, "generate_answer", generate)
    monkeypatch.setattr(qa, "_verify", verify)
    monkeypatch.setattr(qa, "retrieve", AsyncMock(return_value=[context]))
    monkeypatch.setattr(qa, "_finish", AsyncMock())

    async def run():
        return [e async for e in qa._answer_stream(None, req or ChatRequest(message="신고 의무"), analysis, llm.Usage())]

    output = asyncio.run(run())
    payload = next(e["data"] for e in output if e["event"] == "answer")
    return payload, output, generated, seen


@pytest.mark.parametrize("message", [" ", "\n\t", "\u3000"])
def test_whitespace_only_question_is_rejected(message):
    with pytest.raises(ValidationError):
        ChatRequest(message=message)


def test_message_history_and_document_are_masked_before_any_llm(monkeypatch):
    req = ChatRequest(message=f"연락처 {PHONE}로 안내해주세요", history=[
        {"role": "user", "content": "외국인등록번호 900101-5123456입니다"},
        {"role": "assistant", "content": "여권 M12345678을 확인하세요"},
    ])
    analysis = qa.AnalysisContext(uuid4(), f"문서 연락처 {PHONE}", f"문서 요약 {PHONE}", None)
    _, _, _, seen = events(monkeypatch, [answer()], req, analysis)
    received = str(seen)
    assert PHONE not in received
    assert "900101-5123456" not in received
    assert "M12345678" not in received
    assert "가림" in received
    assert PHONE in req.message  # API 입력 객체 자체는 변경하지 않는다


@pytest.mark.parametrize("bad", [
    answer(f"{CLAIM} [1].", (2,)),
    answer(f"{CLAIM}.", ()),
    answer(f"안내 [1]. {CLAIM} [2].", (1,)),
    answer(f"{CLAIM} [1].", (1, 1)),
], ids=["orphan", "no-citations", "partial-orphan", "ambiguous-duplicate"])
def test_unresolved_citations_retry_once_then_hide_unsupported_claim(monkeypatch, bad):
    payload, output, generated, _ = events(monkeypatch, [bad])
    assert len(generated) == 2
    assert sum(e["event"] == "reset" for e in output) == 1
    assert CLAIM not in payload["answer"]
    assert payload["citations"] == []
    assert payload["confidence"] == "low" and payload["needs_expert"]
    assert "1345" in payload["answer"]


def test_corrected_citations_after_retry_are_published(monkeypatch):
    payload, _, generated, _ = events(monkeypatch, [answer("안내 [1].", (2,)), answer()])
    assert len(generated) == 2
    assert payload["citations"][0]["verified"] is True
    assert payload["answer"] == "조문을 확인하세요 [1]."
    assert payload["confidence"] == "high"


def test_valid_citations_do_not_request_an_extra_generation(monkeypatch):
    payload, _, generated, _ = events(monkeypatch, [answer()])
    assert len(generated) == 1 and len(payload["citations"]) == 1
