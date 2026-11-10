import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import documents as api
from app.core.db import get_session

CID = "test-client-0001"
OTHER = "test-client-0002"


def bare_client() -> TestClient:
    """DB 없이 검증 단계만 확인한다."""
    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")

    async def no_db():
        yield None

    app.dependency_overrides[get_session] = no_db
    return TestClient(app)


def test_client_id_required():
    c = bare_client()
    assert c.get("/api/v1/documents").status_code == 400
    assert c.get("/api/v1/documents", headers={"X-Client-Id": "short"}).status_code == 400


def test_unsupported_file_rejected_before_db():
    r = bare_client().post("/api/v1/documents", headers={"X-Client-Id": CID},
                           files={"file": ("a.txt", b"hello" * 20, "text/plain")}, data={"lang": "ko"})
    assert r.status_code == 415


def test_samples_listed():
    r = bare_client().get("/api/v1/documents/samples")
    assert {s["id"] for s in r.json()} == {"extension-guide", "address-report"}


# --- 아래는 DB + 가짜 LLM으로 전체 흐름을 돈다 -------------------------------------------

@pytest.fixture
def client():
    from app.core.db import engine
    from app.main import app

    with TestClient(app) as c:
        yield c
        c.portal.call(engine.dispose)  # 테스트마다 이벤트 루프가 바뀌므로 연결을 닫아 둔다


def _wait(c, aid, headers, until, timeout=30):
    for _ in range(timeout * 4):
        body = c.get(f"/api/v1/documents/{aid}", headers=headers).json()
        if body["status"] in until:
            return body
        time.sleep(0.25)
    raise AssertionError(f"{until} 상태가 되지 않음: {body['status']}")


@pytest.mark.db
def test_full_document_flow(client, demo_dir):
    h = {"X-Client-Id": CID}
    data = (demo_dir / "sample-extension-guide.docx").read_bytes()
    r = client.post("/api/v1/documents", headers=h, data={"lang": "vi"},
                    files={"file": ("guide.docx", data, api.DOCX)})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["status"] == "questions" and a["intake"]["questions"]
    aid = a["id"]

    # 다른 브라우저 ID로는 보이지 않는다
    assert client.get(f"/api/v1/documents/{aid}", headers={"X-Client-Id": OTHER}).status_code == 404
    assert aid not in [x["id"] for x in client.get("/api/v1/documents", headers={"X-Client-Id": OTHER}).json()]

    # 답변이 빠지면 422와 빠진 질문 ID
    r = client.post(f"/api/v1/documents/{aid}/answers", headers=h, json={"answers": []})
    assert r.status_code == 422 and r.json()["missing_question_ids"]

    answers = [{"question_id": q["id"], "option_id": q["options"][0]["id"]} for q in a["intake"]["questions"]]
    r = client.post(f"/api/v1/documents/{aid}/answers", headers=h, json={"answers": answers})
    assert r.status_code == 202 and r.json()["status"] == "analyzing"

    body = _wait(client, aid, h, {"review", "failed"})
    assert body["status"] == "review", body.get("error")
    assert body["result"]["next_actions"] and len(body["checklist"]) == len(body["result"]["next_actions"])

    for item in body["checklist"]:
        r = client.post(f"/api/v1/documents/{aid}/checklist", headers=h, json={"index": item["index"], "done": True})
        assert r.status_code == 200
    assert r.json()["status"] == "done"
    # 다 끝난 건은 취소·재분석할 수 없다
    assert client.post(f"/api/v1/documents/{aid}/cancel", headers=h).status_code == 409
    assert client.post(f"/api/v1/documents/{aid}/answers", headers=h, json={"answers": answers}).status_code == 409
    r = client.post(f"/api/v1/documents/{aid}/checklist", headers=h, json={"index": 0, "done": False})
    assert r.json()["status"] == "review"
    assert client.delete(f"/api/v1/documents/{aid}", headers=h).status_code == 204
    assert client.get(f"/api/v1/documents/{aid}", headers=h).status_code == 404


@pytest.mark.db
def test_cancel_during_analysis_discards_late_result(client):
    h = {"X-Client-Id": CID}
    a = client.post("/api/v1/documents/samples/address-report", headers=h, data={"lang": "ko"}).json()
    answers = [{"question_id": q["id"], "option_id": q["options"][0]["id"]} for q in a["intake"]["questions"]]
    client.post(f"/api/v1/documents/{a['id']}/answers", headers=h, json={"answers": answers})
    r = client.post(f"/api/v1/documents/{a['id']}/cancel", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "canceled"
    time.sleep(4)  # 가짜 분석(3초)이 끝난 뒤에도 취소 상태를 유지한다
    body = client.get(f"/api/v1/documents/{a['id']}", headers=h).json()
    assert body["status"] == "canceled" and body["result"] is None


@pytest.mark.db
def test_identifiers_are_masked(client):
    import io

    from docx import Document

    doc = Document()
    doc.add_paragraph("체류기간 연장 신청 안내입니다. 외국인등록번호 900101-5123456, 연락처 010-1234-5678로 연락 바랍니다.")
    buf = io.BytesIO()
    doc.save(buf)
    h = {"X-Client-Id": CID}
    a = client.post("/api/v1/documents", headers=h, data={"lang": "ko"},
                    files={"file": ("m.docx", buf.getvalue(), api.DOCX)}).json()
    assert a["masked_count"] == 2
    assert "5123456" not in str(a) and "5678" not in str(a)


@pytest.mark.db
def test_health_and_provision(client):
    h = client.get("/health").json()
    assert h["llm_fake"] is True and h["provisions"] > 1000
    p = client.get("/api/v1/provisions", params={"id": "출입국관리법:J25"}).json()
    assert p["number_label"] == "제25조(체류기간 연장허가)" and p["effective"]
    rel = client.get("/api/v1/provisions/related", params={"id": "출입국관리법:J25"}).json()
    assert any(r["rel"] == "GUIDES" and r["direction"] == "incoming" for r in rel)


@pytest.mark.db
def test_chat_answer_cites_real_provision(client):
    r = client.post("/api/v1/chat", json={"message": "체류기간 연장허가는 언제까지 신청해야 하나요?", "lang": "ko"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["citations"] and all(c["verified"] for c in body["citations"])
    assert "1345" in body["disclaimer"]


@pytest.mark.db
def test_greeting_is_not_searched(client):
    r = client.post("/api/v1/chat", json={"message": "ㅎㅇ", "lang": "ko"})
    body = r.json()
    assert r.status_code == 200
    assert body["kind"] == "smalltalk"
    assert body["citations"] == [] and body["sources"] == [] and body["search_queries"] == []
    assert len(body["follow_up_questions"]) == 3
