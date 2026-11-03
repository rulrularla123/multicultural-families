"""US-01 1~5번 중 표시 언어를 제외한 서버 생성·목록 자체 점검."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.main import create_app
from app.models import Attachment, PreparationCase


USER = {"X-Demo-Account": "demo-user-1"}
OTHER = {"X-Demo-Account": "demo-user-2"}
OFFICER = {"X-Demo-Account": "demo-officer"}
PDF = b"%PDF-1.4\n%%EOF"
MAX_BYTES = 10_485_760


def counts(factory):
    with factory() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (PreparationCase, Attachment))


def create(client, *, situation="체류 연장 준비", support_type="F-6-1", files=None, headers=USER, extra=None):
    data = {"support_type": support_type, "situation": situation, **(extra or {})}
    uploads = files if files is not None else [("files", ("mock.pdf", PDF, "application/pdf"))]
    return client.post("/cases", headers=headers, data=data, files=uploads)


def test_us01_create_persists_pdf_and_only_lists_owner_cases(client, factory):
    before = counts(factory)
    response = create(client)
    assert response.status_code == 201
    body = response.json()
    assert body["ok"] is True
    summary = body["case"]
    assert summary["owner_id"] == "demo-user-1"
    assert summary["support_type"] == "F-6-1"
    assert summary["status"] == "준비중"
    assert datetime.fromisoformat(summary["created_at"]).tzinfo is not None
    assert counts(factory) == (before[0] + 1, before[1] + 1)
    with factory() as session:
        case = session.get(PreparationCase, summary["id"])
        attachment = session.scalar(select(Attachment).where(Attachment.case_id == case.id))
        assert case.display_language is None
        assert case.situation == "체류 연장 준비"
        assert attachment.filename == "mock.pdf"
        assert attachment.file_data == PDF
        assert attachment.size_bytes == len(PDF)
        assert attachment.document_version == case.document_version == 1
        assert attachment.extracted_text is None
    listing = client.get("/cases", headers=USER)
    assert listing.status_code == 200
    assert listing.json()[0] == summary
    assert all(item["owner_id"] == "demo-user-1" for item in listing.json())
    assert summary["id"] not in [item["id"] for item in client.get("/cases", headers=OTHER).json()]
    detail = client.get(f"/cases/{summary['id']}", headers=USER)
    assert detail.status_code == 200
    assert detail.json()["display_language"] is None
    assert "file_data" not in detail.json()
    assert "analysis_items" not in detail.json()
    assert client.get(f"/cases/{summary['id']}", headers=OTHER).status_code == 403


@pytest.mark.parametrize("situation", ["가", "가" * 1000, "가" * 999 + "🙂"])
def test_us01_situation_boundaries_are_unicode_code_points(client, situation):
    assert create(client, situation=situation).status_code == 201


@pytest.mark.parametrize("situation", ["", " \n\t　", "가" * 1001, "가" * 1000 + "🙂", " " + "가" * 1000])
def test_us01_invalid_situation_does_not_create_partial_data(client, factory, situation):
    before = counts(factory)
    response = create(client, situation=situation)
    assert response.status_code == 422
    assert response.json()["ok"] is False
    assert any(item["field"] == "situation" for item in response.json()["errors"])
    assert counts(factory) == before


def test_us01_preserves_spaces_and_line_breaks_in_original_situation(client, factory):
    original = " 가\n나 "
    response = create(client, situation=original)
    assert response.status_code == 201
    with factory() as session:
        assert session.get(PreparationCase, response.json()["case"]["id"]).situation == original


@pytest.mark.parametrize("count", [1, 5])
def test_us01_accepts_file_count_boundaries(client, factory, count):
    files = [("files", (f"{index}.PDF", PDF, "application/octet-stream")) for index in range(count)]
    response = create(client, files=files)
    assert response.status_code == 201
    with factory() as session:
        saved = list(session.scalars(select(Attachment).where(Attachment.case_id == response.json()["case"]["id"])))
        assert len(saved) == count


@pytest.mark.parametrize("count", [0, 6, 7])
def test_us01_rejects_invalid_file_count_without_partial_data(client, factory, count):
    before = counts(factory)
    files = [("files", (f"{index}.pdf", PDF, "application/pdf")) for index in range(count)]
    response = create(client, files=files)
    assert response.status_code == 422
    assert any(item["field"] == "files" for item in response.json()["errors"])
    assert counts(factory) == before


def test_us01_accepts_exact_ten_megabytes(client, factory):
    content = b"%PDF-" + b" " * (MAX_BYTES - 5)
    response = create(client, files=[("files", ("boundary.pdf", content, "application/pdf"))])
    assert response.status_code == 201
    with factory() as session:
        attachment = session.scalar(select(Attachment))
        assert attachment.size_bytes == MAX_BYTES
        assert attachment.file_data == content


@pytest.mark.parametrize("filename,content", [
    ("too-big.pdf", b"%PDF-" + b" " * (MAX_BYTES - 4)),
    ("not-pdf.txt", PDF), ("fake.pdf", b"not a PDF"), ("empty.pdf", b""),
    ("x" * 256 + ".pdf", PDF),
])
def test_us01_rejects_bad_file_without_partial_data(client, factory, filename, content):
    before = counts(factory)
    response = create(client, files=[("files", (filename, content, "application/pdf"))])
    assert response.status_code == 422
    assert any(item["field"] == "files" for item in response.json()["errors"])
    assert counts(factory) == before


def test_us01_mixed_valid_and_invalid_files_are_atomic(client, factory):
    before = counts(factory)
    response = create(client, files=[("files", ("ok.pdf", PDF)), ("files", ("bad.pdf", b"bad"))])
    assert response.status_code == 422
    assert counts(factory) == before


@pytest.mark.parametrize("support_type", ["F-6-2", "", "F-6-1 "])
def test_us01_rejects_unsupported_type(client, factory, support_type):
    before = counts(factory)
    response = create(client, support_type=support_type)
    assert response.status_code == 422
    assert any(item["field"] == "support_type" for item in response.json()["errors"])
    assert counts(factory) == before


@pytest.mark.parametrize("extra", [{"owner_id": "demo-user-2"}, {"status": "준비 확인 완료"}, {"display_language": "unapproved"}])
def test_us01_rejects_unknown_or_forged_fields(client, factory, extra):
    before = counts(factory)
    assert create(client, extra=extra).status_code == 422
    assert counts(factory) == before


@pytest.mark.parametrize("headers,status", [({}, 401), ({"X-Demo-Account": "unknown"}, 401), (OFFICER, 403)])
def test_us01_creation_and_owner_list_require_user(client, factory, headers, status):
    before = counts(factory)
    assert create(client, headers=headers).status_code == status
    assert client.get("/cases", headers=headers).status_code == status
    assert counts(factory) == before


def test_us01_query_parameter_cannot_change_owner_filter(client):
    response = client.get("/cases?owner_id=demo-user-2", headers=USER)
    assert response.status_code == 200
    assert all(item["owner_id"] == "demo-user-1" for item in response.json())


def test_us01_attachment_save_failure_rolls_back_case(engine, factory):
    before = counts(factory)

    def fail_attachment(session, flush_context, instances):
        if any(isinstance(item, Attachment) for item in session.new):
            raise RuntimeError("첨부 저장 실패 모의 시험")

    event.listen(factory, "before_flush", fail_attachment)
    try:
        with TestClient(create_app(engine=engine, demo_mode=True), raise_server_exceptions=False) as client:
            client.app.state.session_factory = factory
            assert create(client).status_code == 500
    finally:
        event.remove(factory, "before_flush", fail_attachment)
    assert counts(factory) == before


def test_us01_non_multipart_body_is_rejected(client, factory):
    before = counts(factory)
    assert client.post("/cases", headers=USER, json={"support_type": "F-6-1", "situation": "가"}).status_code == 422
    assert counts(factory) == before


def test_us01_binary_pdf_is_preserved_without_text_decoding(client, factory):
    content = b"%PDF-1.4\n\x00\xff\x80\x01'\\\n%%EOF"
    response = create(client, files=[("files", ("binary.pdf", content, "application/octet-stream"))])
    assert response.status_code == 201
    with factory() as session:
        assert session.scalar(select(Attachment)).file_data == content
