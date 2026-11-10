"""인수 조건 회귀 테스트 (US-01·02·03·04·05·06).

기대값은 docs/requirements/backlog.md 인수 조건과 docs/API.md 상태 코드에서만 가져온다.
기존 test_documents_api.py가 다루는 정상 흐름은 반복하지 않고, 실패·경계·권한 경로를 채운다.
LLM은 conftest의 LLM_FAKE를 쓰고, 실패는 테스트 안에서 분석 함수를 바꿔 재현한다.
"""
import io
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.api.v1 import documents as api
from app.core.db import get_session
from app.documents.extract import MAX_BYTES, PDF, UnsupportedDocument, extract_text

CID = "regression-client-01"
OTHER = "regression-client-02"
H = {"X-Client-Id": CID}
H_OTHER = {"X-Client-Id": OTHER}
PHONE = "010-9876-5432"


# --- 입력 파일 ------------------------------------------------------------------------

def text_pdf(text: str = "Thong bao gia han luu tru. Han nop ho so.", size: int | None = None) -> bytes:
    """글자가 있는 PDF. size를 주면 내용 스트림의 주석 줄로 전체 크기를 정확히 맞춘다."""
    def build(pad: int) -> bytes:
        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        body = f"BT /F1 12 Tf 10 200 Td ({text}) Tj ET\n"
        stream.set_data((body + ("%" + "0" * (pad - 2) + "\n" if pad >= 2 else "")).encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    if size is None:
        return build(0)
    pad = size - len(build(0))
    for _ in range(5):  # 길이 자릿수가 바뀌면 몇 바이트 달라지므로 맞을 때까지 고친다
        data = build(pad)
        if len(data) == size:
            return data
        pad += size - len(data)
    raise AssertionError("PDF 크기를 맞추지 못함")


def blank_pdf() -> bytes:
    """글자가 없는 PDF (스캔·이미지 PDF와 같이 추출할 글자가 없음)."""
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def bare_client() -> TestClient:
    """DB 없이 업로드 검증 단계만 확인한다."""
    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")

    async def no_db():
        yield None

    app.dependency_overrides[get_session] = no_db
    return TestClient(app)


# --- US-03 경계: DB 없이 -----------------------------------------------------------------

def test_us03_pdf_exactly_10485760_bytes_is_accepted_by_extraction():
    """US-03 (경계): 정확히 10MB(10,485,760바이트) 파일은 받는다."""
    data = text_pdf(size=MAX_BYTES)
    assert len(data) == 10_485_760
    assert "Thong bao" in extract_text("a.pdf", PDF, data, "ko").text


def test_us03_pdf_10485761_bytes_is_rejected_with_413():
    """US-03 (경계): 10,485,761바이트는 거절한다(API.md 413)."""
    data = text_pdf(size=MAX_BYTES + 1)
    assert len(data) == 10_485_761
    r = bare_client().post("/api/v1/documents", headers=H, data={"lang": "ko"},
                           files={"file": ("a.pdf", data, PDF)})
    assert r.status_code == 413 and r.json()["detail"]


def test_us03_pdf_without_text_is_rejected_with_reason():
    """US-03 (실패): 글자를 추출할 수 없는 파일(스캔·이미지 PDF 포함)은 이유와 함께 거절한다(API.md 422)."""
    with pytest.raises(UnsupportedDocument) as e:
        extract_text("scan.pdf", PDF, blank_pdf(), "vi")
    assert e.value.status == 422 and str(e.value)


# --- DB + 가짜 LLM -------------------------------------------------------------------------

@pytest.fixture
def client():
    from app.core.db import engine
    from app.main import app

    with TestClient(app) as c:
        yield c
        c.portal.call(engine.dispose)


def _ids(c, headers=H):
    return [x["id"] for x in c.get("/api/v1/documents", headers=headers).json()]


def _sample(c, headers=H, lang="ko"):
    r = c.post("/api/v1/documents/samples/address-report", headers=headers, data={"lang": lang})
    assert r.status_code == 201, r.text
    return r.json()


def _answers(analysis):
    return [{"question_id": q["id"], "option_id": q["options"][0]["id"]} if q["options"]
            else {"question_id": q["id"], "text": "예"} for q in analysis["intake"]["questions"]]


def _wait(c, aid, until, headers=H, timeout=30):
    body = None
    for _ in range(timeout * 4):
        body = c.get(f"/api/v1/documents/{aid}", headers=headers).json()
        if body["status"] in until:
            return body
        time.sleep(0.25)
    raise AssertionError(f"{until} 상태가 되지 않음: {body and body['status']}")


def _reviewed(c):
    a = _sample(c)
    c.post(f"/api/v1/documents/{a['id']}/answers", headers=H, json={"answers": _answers(a)})
    return _wait(c, a["id"], {"review"})


@pytest.mark.db
@pytest.mark.parametrize("name, data, mime, status", [
    ("a.txt", b"hello" * 20, "text/plain", 415),
    ("big.pdf", None, PDF, 413),
    ("scan.pdf", None, PDF, 422),
], ids=["not-pdf-docx", "over-10mb", "no-text"])
def test_us03_rejected_upload_creates_no_analysis(client, name, data, mime, status):
    """US-03 (실패): 지원하지 않는 파일·10MB 초과·글자 없는 파일은 분석 건을 만들지 않고 이유를 표시한다."""
    if data is None:
        data = text_pdf(size=MAX_BYTES + 1) if status == 413 else blank_pdf()
    before = _ids(client)
    r = client.post("/api/v1/documents", headers=H, data={"lang": "vi"}, files={"file": (name, data, mime)})
    assert r.status_code == status and r.json()["detail"]
    assert _ids(client) == before


@pytest.mark.db
def test_us03_missing_answers_keep_questions_status(client):
    """US-03 (실패): 필수 질문에 답하지 않으면 분석을 시작하지 않고 빠진 질문을 표시한다. 상태는 질문 대기."""
    a = _sample(client)
    partial = _answers(a)[:-1]
    r = client.post(f"/api/v1/documents/{a['id']}/answers", headers=H, json={"answers": partial})
    assert r.status_code == 422
    assert r.json()["missing_question_ids"] == [a["intake"]["questions"][-1]["id"]]
    assert client.get(f"/api/v1/documents/{a['id']}", headers=H).json()["status"] == "questions"


@pytest.fixture
def llm_calls(monkeypatch):
    """가짜 LLM에 들어가는 요청을 기록한다 (보내는 내용만 보고, 응답은 그대로 가짜 응답)."""
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


@pytest.mark.db
def test_us03_intake_request_has_masked_text_without_client_id(client, llm_calls):
    """US-03 (LLM): 서류 파악·질문 생성 요청에는 마스킹한 추출 텍스트만 있고 익명 ID는 없다."""
    from docx import Document

    doc = Document()
    doc.add_paragraph(f"체류기간 연장 신청 안내입니다. 연락처 {PHONE}로 연락 바랍니다.")
    buf = io.BytesIO()
    doc.save(buf)
    r = client.post("/api/v1/documents", headers=H, data={"lang": "ko"},
                    files={"file": ("m.docx", buf.getvalue(), api.DOCX)})
    assert r.status_code == 201, r.text
    assert llm_calls, "LLM 요청이 기록되지 않음"
    sent = "\n".join(llm_calls)
    assert "체류기간 연장 신청 안내" in sent
    assert PHONE not in sent and "9876" not in sent
    assert CID not in sent


# --- US-04 분석 실패와 다시 시도 -------------------------------------------------------------

@pytest.mark.db
def test_us04_llm_error_sets_failed_and_retry_reanalyzes_with_same_answers(client, monkeypatch):
    """US-04 (실패): LLM 오류면 분석 실패가 되고, 다시 시도하면 같은 답변으로 다시 분석한다."""
    from app.services import documents as svc

    real = svc.run_analysis

    async def broken(*args, **kwargs):
        raise RuntimeError("LLM 오류 재현")

    a = _sample(client)
    answers = _answers(a)
    monkeypatch.setattr(svc, "run_analysis", broken)
    client.post(f"/api/v1/documents/{a['id']}/answers", headers=H, json={"answers": answers})
    failed = _wait(client, a["id"], {"failed", "review"})
    assert failed["status"] == "failed" and failed["error"] and failed["result"] is None

    monkeypatch.setattr(svc, "run_analysis", real)
    r = client.post(f"/api/v1/documents/{a['id']}/answers", headers=H, json={"answers": []})
    assert r.status_code == 202 and r.json()["status"] == "analyzing"
    done = _wait(client, a["id"], {"review", "failed"})
    assert done["status"] == "review"
    assert [(x["question_id"], x.get("option_id")) for x in done["answers"]] == \
        [(x["question_id"], x.get("option_id")) for x in answers]


# --- US-05 체크리스트 -----------------------------------------------------------------------

@pytest.mark.db
def test_us05_checklist_before_review_is_409(client):
    """US-05 (실패): 결과 확인·완료가 아닌 건의 체크리스트는 바꿀 수 없다(409)."""
    a = _sample(client)
    r = client.post(f"/api/v1/documents/{a['id']}/checklist", headers=H, json={"index": 0, "done": True})
    assert r.status_code == 409
    assert client.get(f"/api/v1/documents/{a['id']}", headers=H).json()["status"] == "questions"


@pytest.mark.db
def test_us05_unknown_checklist_index_is_422_and_keeps_saved_checks(client):
    """US-05 (실패): 없는 항목 번호는 거절하고(422) 저장된 체크는 그대로 둔다."""
    b = _reviewed(client)
    aid = b["id"]
    client.post(f"/api/v1/documents/{aid}/checklist", headers=H, json={"index": 0, "done": True})
    saved = client.get(f"/api/v1/documents/{aid}", headers=H).json()["checklist"]
    for index in (len(saved), -1):
        r = client.post(f"/api/v1/documents/{aid}/checklist", headers=H, json={"index": index, "done": True})
        assert r.status_code == 422
    assert client.get(f"/api/v1/documents/{aid}", headers=H).json()["checklist"] == saved


@pytest.mark.db
def test_us05_checks_persist_after_reload(client):
    """US-05 (정상): 체크하면 저장되어 다시 불러와도 유지된다."""
    b = _reviewed(client)
    client.post(f"/api/v1/documents/{b['id']}/checklist", headers=H, json={"index": 0, "done": True})
    again = client.get(f"/api/v1/documents/{b['id']}", headers=H).json()
    assert again["checklist"][0]["done"] is True and again["status"] == "review"


# --- US-06 내 분석 건 관리 ------------------------------------------------------------------

@pytest.mark.db
def test_us06_list_is_newest_first_and_only_mine(client):
    """US-06 (정상): 내 익명 ID의 건만 최신순으로 보인다."""
    first = _sample(client)["id"]
    second = _sample(client)["id"]
    other = _sample(client, headers=H_OTHER)["id"]
    ids = _ids(client)
    assert ids.index(second) < ids.index(first)
    assert other not in ids


@pytest.mark.db
def test_us06_other_client_cannot_cancel_or_delete(client):
    """US-06 (실패): 다른 익명 ID의 건은 취소·삭제가 안 된다(404). 원래 건은 그대로다."""
    a = _sample(client)
    assert client.post(f"/api/v1/documents/{a['id']}/cancel", headers=H_OTHER).status_code == 404
    assert client.delete(f"/api/v1/documents/{a['id']}", headers=H_OTHER).status_code == 404
    assert client.get(f"/api/v1/documents/{a['id']}", headers=H).json()["status"] == "questions"


@pytest.mark.db
def test_us06_cancel_from_questions_and_review(client):
    """US-06 (정상): 질문 대기·결과 확인 건을 취소하면 취소됨이 된다. (분석중 취소는 test_documents_api.py)"""
    q = _sample(client)
    r = client.post(f"/api/v1/documents/{q['id']}/cancel", headers=H)
    assert r.status_code == 200 and r.json()["status"] == "canceled"
    b = _reviewed(client)
    r = client.post(f"/api/v1/documents/{b['id']}/cancel", headers=H)
    assert r.status_code == 200 and r.json()["status"] == "canceled"


@pytest.mark.db
def test_us06_canceled_cannot_be_canceled_again_but_can_be_deleted(client):
    """US-06 (실패): 취소됨 건은 다시 취소할 수 없다(409). 삭제는 가능하고 목록에서 사라진다."""
    a = _sample(client)
    client.post(f"/api/v1/documents/{a['id']}/cancel", headers=H)
    assert client.post(f"/api/v1/documents/{a['id']}/cancel", headers=H).status_code == 409
    assert client.post(f"/api/v1/documents/{a['id']}/answers", headers=H,
                       json={"answers": _answers(a)}).status_code == 409
    assert client.delete(f"/api/v1/documents/{a['id']}", headers=H).status_code == 204
    assert a["id"] not in _ids(client)


# --- US-01 질문 입력, US-02 없는 조문 -------------------------------------------------------

@pytest.mark.db
@pytest.mark.parametrize("message", ["", "가" * 1001], ids=["empty", "1001-chars"])
def test_us01_empty_or_too_long_question_is_422(client, message):
    """US-01 (실패): 빈 질문, 1,000자 초과는 거절한다(API.md 422)."""
    assert client.post("/api/v1/chat", json={"message": message, "lang": "vi"}).status_code == 422


@pytest.mark.db
def test_us01_whitespace_only_question_is_422(client):
    """US-01 (실패): 공백만 있는 질문은 거절한다."""
    assert client.post("/api/v1/chat", json={"message": "   \n ", "lang": "vi"}).status_code == 422


@pytest.mark.db
def test_us01_1000_character_question_is_accepted(client):
    """US-01 (정상): 1~1,000자 질문은 받는다(경계 1,000자)."""
    message = ("체류기간 연장 신청 기한이 궁금합니다. " * 60)[:1000]
    assert len(message) == 1000
    assert client.post("/api/v1/chat", json={"message": message, "lang": "vi"}).status_code == 200


@pytest.mark.db
def test_us01_identifiers_in_question_are_masked_before_llm(client, llm_calls):
    """US-01 (LLM): 질문에 식별정보 패턴이 있으면 마스킹한 질문만 LLM에 보낸다."""
    r = client.post("/api/v1/chat", json={"message": f"제 번호 {PHONE}로 체류기간 연장 안내를 받을 수 있나요?",
                                          "lang": "ko"})
    assert r.status_code == 200
    assert llm_calls and PHONE not in "\n".join(llm_calls)


@pytest.mark.db
def test_us02_unknown_provision_is_404(client):
    """US-02 (실패): 없는 조문 ID를 요청하면 404."""
    r = client.get("/api/v1/provisions", params={"id": "출입국관리법:J99999"})
    assert r.status_code == 404 and r.json()["detail"]
