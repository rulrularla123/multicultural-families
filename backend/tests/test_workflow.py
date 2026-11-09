"""US-02·03·05·07 인수 조건: MySQL 상태 전이·권한·실패·오래된 응답 폐기."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import BytesIO
import json
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app import workflow
from app.common.llm_client import MockTransport
from app.database import prepare_workflow_schema
from app.main import create_app
from app.models import Attachment, CaseApproval, CaseHistory, CheckResult, Criterion, PreparationCase, PreparationItem
from app.routers import cancellation


OWNER = {"X-Demo-Account": "demo-user-1"}
OTHER = {"X-Demo-Account": "demo-user-2"}
OFFICER = {"X-Demo-Account": "demo-officer"}
NOTICE = "Đây không phải là xác nhận tiếp nhận hồ sơ hoặc cấp phép gia hạn lưu trú."


def pdf_bytes(text="Mock document for extension"):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def ready(factory):
    with factory.begin() as session:
        case = session.get(PreparationCase, 1003)
        case.display_language = None
        data = pdf_bytes()
        session.add(Attachment(case_id=1003, filename="mock.pdf", size_bytes=len(data),
                               document_version=1, file_data=data))
        criterion = Criterion(body="개발용 모의 기준입니다. 실제 민원 기준이 아닙니다.",
                              source="https://example.test/mock-rule", checked_on=date(2026, 11, 9),
                              version=1, is_verified=True)
        session.add(criterion)
        session.flush()
        return criterion.id


def checked(client):
    response = client.post("/cases/1003/check", headers=OWNER)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "담당자 승인 대기"
    return client.get("/cases/1003/check-result", headers=OFFICER).json()


def review_body(result, criterion_id=None):
    original = result["analysis_items"]
    return {"result_id": result["result_id"], "reason": "모의 기준과 번역문을 직접 대조해 확인함",
            "translation_confirmed": True,
            "items": [{"id": "reviewed-item", "kind": "additional_documents", "text": "승인할 준비 항목",
                       "criterion_id": str(criterion_id or original[0]["criterion_id"]),
                       "translated_text": "Giấy tờ cần chuẩn bị"}]}


def approved(client):
    result = checked(client)
    response = client.post("/cases/1003/review", headers=OFFICER, json=review_body(result))
    assert response.status_code == 200, response.text
    response = client.post("/cases/1003/approve", headers=OFFICER, json={"result_id": result["result_id"]})
    assert response.status_code == 200, response.text
    return client.get("/cases/1003/approved-result", headers=OWNER).json()


def requested(client, value=True):
    result = approved(client)
    items = [{"id": i["id"], "prepared": value} for i in result["preparation_items"]]
    assert client.post("/cases/1003/preparation-items", headers=OWNER, json={"items": items}).status_code == 200
    assert client.post("/cases/1003/request-confirmation", headers=OWNER).status_code == 200
    return result


def state(factory):
    with factory() as session:
        return session.get(PreparationCase, 1003).status


def test_full_us02_us03_us05_us07_owner_flow(client, factory, ready):
    result = requested(client)
    assert result["display_language"] == "vi" and result["bilingual_ready"]
    assert "승인할 준비 항목" in json.dumps(result, ensure_ascii=False)
    assert "Giấy tờ cần chuẩn bị" in json.dumps(result, ensure_ascii=False)
    assert "모의 점검 결과입니다" not in json.dumps(result, ensure_ascii=False)
    response = client.post("/cases/1003/complete", headers=OFFICER,
                           json={"notice_translation": NOTICE, "translation_confirmed": True})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "준비 확인 완료"
    assert response.json()["notice_translation"] == NOTICE
    assert "+00:00" in response.json()["completed_at"]
    with factory() as session:
        history = session.scalars(select(CaseHistory).where(CaseHistory.case_id == 1003)
                                  .order_by(CaseHistory.id)).all()
        assert [h.to_status for h in history] == ["자동 점검중", "담당자 승인 대기", "담당자 승인 대기", "서류 준비중", "준비 확인 요청", "준비 확인 완료"]
        assert history[3].actor_id == "demo-officer"
        assert history[3].criterion_versions == [{"criterion_id": str(ready), "version": 1}]
        assert session.scalar(select(CaseApproval)).approved_by == "demo-officer"


def test_request_payload_contains_no_accounts_file_data_names_task_or_rejection(client, ready):
    class Capture(MockTransport):
        async def generate(self, payload):
            self.payload = payload
            return await super().generate(payload)
    transport = Capture()
    client.app.state.check_transport = transport
    checked(client)
    assert set(transport.payload) == {"situation", "document_texts", "support_type", "criteria"}
    raw = json.dumps(transport.payload)
    for secret in ("demo-user", "mock.pdf", "task_id", "file_data", "rejection_reason"):
        assert secret not in raw


@pytest.mark.parametrize("kind", ["situation", "document", "broken", "empty", "missing", "no_criteria", "unverified", "criterion_identity", "empty_criterion"])
def test_preflight_failure_leaves_preparing_and_never_calls_llm(client, factory, ready, kind):
    class Never(MockTransport):
        async def generate(self, payload):
            pytest.fail("LLM must not be called")
    client.app.state.check_transport = Never()
    with factory.begin() as session:
        case = session.get(PreparationCase, 1003)
        attachment = session.scalar(select(Attachment).where(Attachment.case_id == 1003))
        criterion = session.get(Criterion, ready)
        if kind == "situation": case.situation = "모의 연락 010-0000-0000"
        if kind == "document": attachment.file_data = pdf_bytes("010-0000-0000")
        if kind == "broken": attachment.file_data = b"%PDF-1.4 broken"
        if kind == "empty": attachment.file_data = pdf_bytes("")
        if kind == "missing": attachment.file_data = None
        if kind == "no_criteria": criterion.is_active = False
        if kind == "unverified": criterion.is_verified = False
        if kind == "criterion_identity": criterion.body = "010-0000-0000"
        if kind == "empty_criterion": criterion.body = " "
    response = client.post("/cases/1003/check", headers=OWNER)
    assert response.status_code in (409, 422)
    assert state(factory) == "준비중"
    assert "010-0000-0000" not in response.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(CheckResult).where(CheckResult.case_id == 1003)) == 0
        assert session.scalar(select(func.count()).select_from(CaseHistory).where(CaseHistory.case_id == 1003)) == 0


@pytest.mark.parametrize("mode,code", [("error", "transport_error"), ("invalid", "invalid_response"), ("delay", "timeout")])
def test_llm_failure_waits_for_officer_and_blocks_approval(client, factory, ready, monkeypatch, mode, code):
    client.app.state.check_transport = MockTransport(mode)
    actual = workflow.check_documents
    async def short_timeout(request, transport, **kwargs):
        return await actual(request, transport, timeout=0.01)
    monkeypatch.setattr(workflow, "check_documents", short_timeout)
    result = checked(client)
    assert result["failure_reason"] == code
    assert client.post("/cases/1003/approve", headers=OFFICER, json={"result_id": result["result_id"]}).status_code == 409
    assert state(factory) == "담당자 승인 대기"
    owner = client.get("/cases/1003", headers=OWNER)
    assert "failure_reason" not in owner.json() and "analysis_items" not in owner.json()
    # 담당자가 근거·처리 사유·번역 확인을 남긴 경우에만 실패 해소 가능.
    assert client.post("/cases/1003/review", headers=OFFICER, json=review_body(result, ready)).status_code == 200
    assert client.post("/cases/1003/approve", headers=OFFICER, json={"result_id": result["result_id"]}).status_code == 200


@pytest.mark.parametrize("criterion_id", [None, "999999"])
def test_unknown_evidence_cannot_be_approved_without_recorded_review(client, factory, ready, criterion_id):
    class Unknown:
        async def generate(self, payload):
            return json.dumps({"cautions": [{"text": "근거 확인 필요", "criterion_id": criterion_id}],
                               "possible_omissions": [], "additional_documents": []})
    client.app.state.check_transport = Unknown()
    result = checked(client)
    assert result["analysis_items"][0]["needs_confirmation"] is True
    assert result["analysis_items"][0]["criterion_id"] is None
    assert client.post("/cases/1003/approve", headers=OFFICER, json={"result_id": result["result_id"]}).status_code == 409
    body = review_body(result, ready)
    assert client.post("/cases/1003/review", headers=OFFICER, json=body).status_code == 200
    assert client.post("/cases/1003/approve", headers=OFFICER, json={"result_id": result["result_id"]}).status_code == 200
    with factory() as session:
        audit = session.scalar(select(CaseHistory).where(CaseHistory.case_id == 1003,
                                CaseHistory.from_status == "담당자 승인 대기",
                                CaseHistory.to_status == "담당자 승인 대기"))
        assert json.loads(audit.reason)["removed_ids"] == [result["analysis_items"][0]["id"]]


@pytest.mark.parametrize("field,value", [("translation_confirmed", False), ("reason", " "), ("items", [])])
def test_translation_review_requires_explicit_officer_confirmation_and_reason(client, ready, field, value):
    result = checked(client)
    body = review_body(result)
    body[field] = value
    assert client.post("/cases/1003/review", headers=OFFICER, json=body).status_code == 422
    assert client.post("/cases/1003/approve", headers=OFFICER, json={"result_id": result["result_id"]}).status_code == 409


def test_unreviewed_vietnamese_translation_blocks_approval(client, ready):
    result = checked(client)
    assert client.post("/cases/1003/approve", headers=OFFICER, json={"result_id": result["result_id"]}).status_code == 409
    body = review_body(result)
    body["items"][0]["translated_text"] = None
    assert client.post("/cases/1003/review", headers=OFFICER, json=body).status_code == 422


@pytest.mark.parametrize("headers,expected", [({}, 401), (OTHER, 403), (OFFICER, 403)])
def test_only_owner_starts_check(client, ready, headers, expected):
    assert client.post("/cases/1003/check", headers=headers).status_code == expected


@pytest.mark.parametrize("path,body", [("check-result", None), ("review", {}), ("approve", {"result_id": 1}),
                                       ("complete", {"notice_translation": NOTICE, "translation_confirmed": True})])
def test_owner_never_reads_draft_or_runs_officer_operations(client, ready, path, body):
    checked(client)
    if body is None:
        assert client.get(f"/cases/1003/{path}", headers=OWNER).status_code == 403
    else:
        # 유효한 본문으로 권한 검사 자체를 확인한다.
        if path == "review":
            result = client.get("/cases/1003/check-result", headers=OFFICER).json()
            body = review_body(result)
        assert client.post(f"/cases/1003/{path}", headers=OWNER, json=body).status_code == 403


@pytest.mark.parametrize("change", ["situation", "document", "criterion", "new_criterion", "inactive", "unverified"])
def test_version_change_blocks_approval_and_publication(client, factory, ready, change):
    result = checked(client)
    assert client.post("/cases/1003/review", headers=OFFICER, json=review_body(result)).status_code == 200
    with factory.begin() as session:
        case = session.get(PreparationCase, 1003)
        criterion = session.get(Criterion, ready)
        if change == "situation": case.situation_version += 1
        if change == "document": case.document_version += 1
        if change == "criterion": criterion.version += 1
        if change == "new_criterion":
            session.add(Criterion(body="추가 모의 기준", source="https://example.test/extra",
                                  checked_on=date(2026, 11, 9), is_verified=True))
        if change == "inactive": criterion.is_active = False
        if change == "unverified": criterion.is_verified = False
    assert client.post("/cases/1003/approve", headers=OFFICER, json={"result_id": result["result_id"]}).status_code == 409
    assert client.get("/cases/1003/approved-result", headers=OWNER).status_code == 409


def test_us05_false_allowed_but_us07_requires_everything_prepared(client, factory, ready):
    requested(client, value=False)
    response = client.post("/cases/1003/complete", headers=OFFICER,
                           json={"notice_translation": NOTICE, "translation_confirmed": True})
    assert response.status_code == 409
    assert state(factory) == "준비 확인 요청"
    assert client.get("/cases/1003/approved-result", headers=OFFICER).json()["not_prepared_count"] == 1


def test_us05_unselected_item_blocks_request(client, factory, ready):
    result = approved(client)
    response = client.post("/cases/1003/request-confirmation", headers=OWNER)
    assert response.status_code == 409
    assert response.json()["detail"]["unselected_item_ids"] == [result["preparation_items"][0]["id"]]
    assert state(factory) == "서류 준비중"


@pytest.mark.parametrize("headers", [OTHER, OFFICER])
def test_only_owner_can_change_prepared_or_request(client, ready, headers):
    result = approved(client)
    item_id = result["preparation_items"][0]["id"]
    assert client.post("/cases/1003/preparation-items", headers=headers,
                       json={"items": [{"id": item_id, "prepared": True}]}).status_code == 403
    assert client.post("/cases/1003/request-confirmation", headers=headers).status_code == 403


@pytest.mark.parametrize("prepared", [None, "true", 1])
def test_prepared_choice_is_strict_boolean(client, ready, prepared):
    result = approved(client)
    assert client.post("/cases/1003/preparation-items", headers=OWNER,
                       json={"items": [{"id": result["preparation_items"][0]["id"], "prepared": prepared}]}).status_code == 422


@pytest.mark.parametrize("flag", ["supplement_resolved", "needs_confirmation"])
def test_unresolved_supplement_or_confirmation_blocks_completion(client, factory, ready, flag):
    requested(client)
    with factory.begin() as session:
        item = session.scalar(select(PreparationItem).where(PreparationItem.case_id == 1003))
        setattr(item, flag, flag == "needs_confirmation")
    response = client.post("/cases/1003/complete", headers=OFFICER,
                           json={"notice_translation": NOTICE, "translation_confirmed": True})
    assert response.status_code == 409
    assert state(factory) == "준비 확인 요청"


def test_completion_requires_confirmed_vietnamese_notice(client, ready):
    requested(client)
    assert client.post("/cases/1003/complete", headers=OFFICER, json={
        "notice_translation": NOTICE, "translation_confirmed": False}).status_code == 409


@pytest.mark.parametrize("change", ["situation", "document", "criterion"])
def test_stale_approval_blocks_check_request_completion_and_read(client, factory, ready, change):
    result = requested(client)
    with factory.begin() as session:
        if change == "criterion": session.get(Criterion, ready).version += 1
        else:
            case = session.get(PreparationCase, 1003)
            setattr(case, change + "_version", 2)
    assert client.get("/cases/1003/approved-result", headers=OWNER).status_code == 409
    assert client.post("/cases/1003/complete", headers=OFFICER,
                       json={"notice_translation": NOTICE, "translation_confirmed": True}).status_code == 409


@pytest.mark.parametrize("end_state", ["준비 확인 완료", "취소 완료"])
def test_terminal_states_reject_every_new_mutation(client, factory, ready, end_state):
    result = approved(client)
    with factory.begin() as session:
        session.get(PreparationCase, 1003).status = end_state
    operations = [
        ("check", None, OWNER), ("review", {"result_id": 1, "reason": "확인", "translation_confirmed": True,
           "items": [{"id": "one", "kind": "cautions", "text": "확인", "translated_text": "x", "criterion_id": str(ready)}]}, OFFICER),
        ("approve", {"result_id": 1}, OFFICER),
        ("preparation-items", {"items": [{"id": result["preparation_items"][0]["id"], "prepared": True}]}, OWNER),
        ("request-confirmation", None, OWNER),
        ("complete", {"notice_translation": NOTICE, "translation_confirmed": True}, OFFICER),
    ]
    for endpoint, body, headers in operations:
        assert client.post(f"/cases/1003/{endpoint}", headers=headers, json=body).status_code == 409
    assert state(factory) == end_state


@pytest.mark.parametrize("change", ["cancel", "situation", "document", "criterion", "task"])
def test_late_llm_result_dropped_after_cancel_or_version_change(engine, factory, ready, change):
    started, release = threading.Event(), threading.Event()
    class Blocking(MockTransport):
        async def generate(self, payload):
            started.set()
            await asyncio.to_thread(release.wait, 10)
            return await super().generate(payload)
    app = create_app(engine=engine, demo_mode=True)
    app.include_router(cancellation.router)
    with TestClient(app) as client:
        client.app.state.check_transport = Blocking()
        with ThreadPoolExecutor() as pool:
            future = pool.submit(client.post, "/cases/1003/check", headers=OWNER)
            try:
                assert started.wait(5)
                # 별도 DB 연결의 변경이 LLM 대기 중에도 완료되어야 한다.
                if change == "cancel":
                    assert client.post("/cases/1003/cancel", headers=OWNER).status_code == 200
                else:
                    with factory.begin() as session:
                        case = session.get(PreparationCase, 1003)
                        if change == "criterion": session.get(Criterion, ready).version += 1
                        if change in {"situation", "document"}: setattr(case, change + "_version", 2)
                        if change == "task": case.current_check_task_id = "new-task"
            finally:
                release.set()
            response = future.result(timeout=10)
    assert response.status_code == 200
    assert response.json()["discarded"] is True
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(CheckResult).where(CheckResult.case_id == 1003)) == 0
        assert session.get(PreparationCase, 1003).status == ("취소 완료" if change == "cancel" else "자동 점검중")


def test_two_simultaneous_checks_start_only_once(engine, factory, ready):
    started, release = threading.Event(), threading.Event()
    class Blocking(MockTransport):
        async def generate(self, payload):
            started.set()
            await asyncio.to_thread(release.wait, 10)
            return await super().generate(payload)
    with TestClient(create_app(engine=engine, demo_mode=True)) as client:
        client.app.state.check_transport = Blocking()
        with ThreadPoolExecutor() as pool:
            first = pool.submit(client.post, "/cases/1003/check", headers=OWNER)
            try:
                assert started.wait(5)
                assert client.post("/cases/1003/check", headers=OWNER).status_code == 409
            finally:
                release.set()
            assert first.result(timeout=10).status_code == 200
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(CheckResult).where(CheckResult.case_id == 1003)) == 1


def test_approval_audit_failure_rolls_back_state_items_and_approval(engine, factory, client, ready):
    result = checked(client)
    assert client.post("/cases/1003/review", headers=OFFICER, json=review_body(result)).status_code == 200
    def fail(session, context, instances):
        if any(isinstance(i, CaseApproval) for i in session.new):
            raise RuntimeError("mock write failure")
    event.listen(factory, "before_flush", fail)
    try:
        with TestClient(create_app(engine=engine, demo_mode=True), raise_server_exceptions=False) as api:
            api.app.state.session_factory = factory
            response = api.post("/cases/1003/approve", headers=OFFICER, json={"result_id": result["result_id"]})
        assert response.status_code == 500
    finally:
        event.remove(factory, "before_flush", fail)
    assert state(factory) == "담당자 승인 대기"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(CaseApproval)) == 0
        assert session.scalar(select(func.count()).select_from(PreparationItem)) == 0


def test_workflow_schema_prepare_is_idempotent_and_preserves_old_rows(engine, factory):
    from sqlalchemy import text
    try:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE preparation_cases DROP COLUMN office"))
            connection.execute(text("ALTER TABLE check_results DROP COLUMN reviewed_items"))
            connection.execute(text("ALTER TABLE check_results DROP COLUMN review_reason"))
        assert len(prepare_workflow_schema(engine)) == 3
        assert prepare_workflow_schema(engine) == []
        with factory() as session:
            assert session.get(PreparationCase, 1001).situation
            assert session.scalar(select(CheckResult).where(CheckResult.case_id == 1001)).analysis_items
    finally:
        prepare_workflow_schema(engine)


def test_completed_snapshot_remains_readable_after_later_criterion_change(client, factory, ready):
    requested(client)
    assert client.post("/cases/1003/complete", headers=OFFICER,
                       json={"notice_translation": NOTICE, "translation_confirmed": True}).status_code == 200
    with factory.begin() as session:
        session.get(Criterion, ready).version += 1
    response = client.get("/cases/1003/approved-result", headers=OWNER)
    assert response.status_code == 200
    assert response.json()["completion_notice"]["notice_translation"] == NOTICE
    assert response.json()["items"][0]["source"] == "https://example.test/mock-rule"


def test_invalid_item_id_or_duplicate_choices_are_atomic(client, factory, ready):
    result = approved(client)
    item_id = result["preparation_items"][0]["id"]
    for ids in ([item_id, item_id], [item_id, 999999]):
        assert client.post("/cases/1003/preparation-items", headers=OWNER, json={
            "items": [{"id": i, "prepared": True} for i in ids]}).status_code == 422
    with factory() as session:
        assert session.get(PreparationItem, item_id).prepared is None


def test_stale_approved_result_blocks_check_saving_and_confirmation(client, factory, ready):
    result = approved(client)
    with factory.begin() as session:
        session.get(Criterion, ready).version += 1
    assert client.post("/cases/1003/preparation-items", headers=OWNER, json={
        "items": [{"id": result["preparation_items"][0]["id"], "prepared": True}]}).status_code == 409
    assert client.post("/cases/1003/request-confirmation", headers=OWNER).status_code == 409


def test_another_owner_cannot_read_approved_result(client, ready):
    approved(client)
    assert client.get("/cases/1003/approved-result", headers=OTHER).status_code == 403


def test_approval_is_once_only_under_concurrent_requests(client, engine, factory, ready):
    result = checked(client)
    assert client.post("/cases/1003/review", headers=OFFICER, json=review_body(result)).status_code == 200
    with TestClient(create_app(engine=engine, demo_mode=True)) as second:
        def send(api):
            return api.post("/cases/1003/approve", headers=OFFICER,
                            json={"result_id": result["result_id"]}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(send, [client, second])) == [200, 409]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(CaseApproval)) == 1
        assert session.scalar(select(func.count()).select_from(PreparationItem)) == 1


def test_unmatched_office_criterion_not_sent_and_matching_unverified_blocks(client, factory, ready):
    with factory.begin() as session:
        session.add(Criterion(body="관서 확인 전 모의 추가 요구", source="https://example.test/office",
                              checked_on=date(2026, 11, 9), office="모의 관서", is_verified=False))
    with factory.begin() as session:
        session.get(PreparationCase, 1003).office = "모의 관서"
    assert client.post("/cases/1003/check", headers=OWNER).status_code == 409
    with factory.begin() as session:
        session.get(PreparationCase, 1003).office = "다른 모의 관서"
    result = checked(client)
    assert result["criterion_versions"] == [{"criterion_id": str(ready), "version": 1}]
