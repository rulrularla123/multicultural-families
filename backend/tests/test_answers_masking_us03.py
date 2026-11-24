"""개인화 질문 자유 입력 답변의 식별정보 마스킹 (공통 조건·US-03·US-04).

기대값 근거: docs/requirements/backlog.md 공통 조건 "LLM에 보내기 전에 식별정보 패턴(외국인등록번호,
주민등록번호, 여권번호, 휴대전화번호)을 마스킹한다", CLAUDE.md "LLM에 보내는 것은 마스킹한 질문·추출 텍스트,
검색된 조문, 개인화 질문 답변뿐". LLM은 conftest의 LLM_FAKE를 쓴다.
"""
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.document_payload import document_payload

CID = "answers-mask-client-01"
H = {"X-Client-Id": CID}
PHONE = "010-9876-5432"
REGISTRATION = "900101-5123456"
PASSPORT = "M12345678"
DEMO_DOC = Path(__file__).resolve().parents[1] / "data" / "demo" / "demo-extension-supplement-notice.docx"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def client():
    from app.core.db import engine
    from app.main import app

    with TestClient(app) as c:
        yield c
        c.portal.call(engine.dispose)


@pytest.fixture
def llm_calls(monkeypatch):
    """가짜 LLM에 들어가는 요청을 기록한다 (응답은 그대로 가짜 응답)."""
    from app import llm_fake

    calls = []
    for name in ("parse", "parse_stream", "complete"):
        original = getattr(llm_fake, name, None)
        if original is None:
            continue

        def spy(*args, _original=original, **kwargs):
            calls.append(json.dumps([str(a) for a in args] + [str(v) for v in kwargs.values()], ensure_ascii=False))
            return _original(*args, **kwargs)

        monkeypatch.setattr(llm_fake, name, spy)
    return calls


def _upload(c):
    r = c.post("/api/v1/documents", headers=H,
               json=document_payload(DEMO_DOC.name, DOCX_MIME, DEMO_DOC.read_bytes(), "ko"))
    assert r.status_code == 201, r.text
    return r.json()


def _wait(c, aid, until, timeout=30):
    body = None
    for _ in range(timeout * 4):
        body = c.get(f"/api/v1/documents/{aid}", headers=H).json()
        if body["status"] in until:
            return body
        time.sleep(0.25)
    raise AssertionError(f"{until} 상태가 되지 않음: {body and body['status']}")


def _free_text_answers(analysis):
    text = f"제 연락처는 {PHONE}, 외국인등록번호는 {REGISTRATION}, 여권번호는 {PASSPORT}입니다. 배우자와 함께 삽니다."
    return [{"question_id": q["id"], "text": text} for q in analysis["intake"]["questions"]]


@pytest.mark.db
def test_us04_free_text_answers_are_masked_before_analysis_llm(client, llm_calls):
    """공통 조건·US-04 (LLM): 자유 입력 답변의 식별정보 패턴은 분석 요청 LLM에 들어가지 않는다."""
    a = _upload(client)
    llm_calls.clear()

    r = client.post(f"/api/v1/documents/{a['id']}/answers", headers=H, json={"answers": _free_text_answers(a)})
    assert r.status_code == 202, r.text
    _wait(client, a["id"], {"review", "failed"})

    assert llm_calls, "분석 LLM 요청이 기록되지 않음"
    sent = "\n".join(llm_calls)
    assert "배우자와 함께 삽니다" in sent
    for value in (PHONE, REGISTRATION, PASSPORT):
        assert value not in sent


@pytest.mark.db
def test_us03_free_text_answers_are_stored_masked(client):
    """공통 조건·US-03: 저장된 답변에도 식별정보 원래 값이 남지 않는다 (추출 직후 마스킹과 같은 기준)."""
    a = _upload(client)

    r = client.post(f"/api/v1/documents/{a['id']}/answers", headers=H, json={"answers": _free_text_answers(a)})
    assert r.status_code == 202, r.text
    body = _wait(client, a["id"], {"review", "failed"})

    stored = json.dumps(body["answers"], ensure_ascii=False)
    assert "배우자와 함께 삽니다" in stored
    for value in (PHONE, REGISTRATION, PASSPORT):
        assert value not in stored
