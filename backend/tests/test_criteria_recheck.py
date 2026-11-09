"""F-02 / US-02: 기존 기준 API 계약을 유지하며 변경 후 무효화·재점검을 검증한다."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import BytesIO
import threading
import pytest
from sqlalchemy import func, select
from app.common.llm_client import MockTransport
from app.models import Attachment, CaseApproval, CaseHistory, CheckResult, Criterion, PreparationCase

OFFICER = {"X-Demo-Account": "demo-officer"}
OWNER = {"X-Demo-Account": "demo-user-1"}
BODY = {"office": None, "body": "모의 체류 준비 공통 기준",
        "source": "https://example.test/rule", "checked_on": "2026-11-09",
        "is_verified": True, "is_active": True}


def pdf_data():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 100 Td (Mock extension document) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def criterion(factory):
    with factory.begin() as session:
        row = Criterion(body=BODY["body"], source=BODY["source"], checked_on=date(2026, 11, 9),
                        is_verified=True, version=1)
        session.add(row)
        session.flush()
        return row.id


def snapshot(factory):
    with factory() as session:
        return (session.scalar(select(func.count()).select_from(Criterion)),
                [(c.id, c.status, c.current_check_task_id) for c in session.scalars(
                    select(PreparationCase).order_by(PreparationCase.id))],
                session.scalar(select(func.count()).select_from(CaseHistory)))


def test_noop_update_preserves_version_and_histories(client, factory, criterion):
    before = snapshot(factory)
    response = client.post(f"/criteria/{criterion}", headers=OFFICER, json={**BODY, "expected_version": 1})
    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert response.json()["recheck_case_ids"] == []
    assert snapshot(factory) == before


def test_editor_version_conflict_is_rejected_without_case_changes(client, factory, criterion):
    before = snapshot(factory)
    response = client.post(f"/criteria/{criterion}", headers=OFFICER,
                           json={**BODY, "expected_version": 2, "body": "덮어쓰면 안 되는 기준"})
    assert response.status_code == 409
    assert snapshot(factory) == before
    with factory() as session:
        assert session.get(Criterion, criterion).version == 1


def test_history_failure_rolls_back_criterion_and_case_invalidation(client, factory, criterion):
    from sqlalchemy import event
    before = snapshot(factory)
    def fail(session, context, instances):
        if any(isinstance(obj, CaseHistory) for obj in session.new):
            raise RuntimeError("mock history write failure")
    app_session = client.app.state.session_factory.class_
    event.listen(app_session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError, match="mock history write failure"):
            client.post(f"/criteria/{criterion}", headers=OFFICER,
                        json={**BODY, "expected_version": 1, "body": "롤백될 기준"})
    finally:
        event.remove(app_session, "before_flush", fail)
    assert snapshot(factory) == before
    with factory() as session:
        assert session.get(Criterion, criterion).version == 1


def test_change_invalidates_result_approval_and_confirmation_but_preserves_finished_cases(client, factory, criterion):
    with factory.begin() as session:
        case = session.get(PreparationCase, 1003)
        case.status, case.current_check_task_id = "준비 확인 요청", "old-task"
        result = CheckResult(case_id=case.id, situation_version=1, document_version=1, task_id="old-task",
                             analysis_items=[], criterion_versions=[{"criterion_id": str(criterion), "version": 1}])
        session.add(result)
        session.flush()
        approval = CaseApproval(case_id=case.id, result_id=result.id, situation_version=1, document_version=1,
                                criterion_versions=result.criterion_versions, items=[], approved_by="demo-officer")
        session.add(approval)
        session.flush()
        result_id, approval_id = result.id, approval.id
    response = client.post(f"/criteria/{criterion}", headers=OFFICER,
                           json={**BODY, "expected_version": 1, "body": "새 모의 기준"})
    assert response.status_code == 200
    assert 1003 in response.json()["recheck_case_ids"]
    with factory() as session:
        case = session.get(PreparationCase, 1003)
        assert case.status == "준비중" and case.current_check_task_id is None  # PDF가 없어 새 점검은 시작하지 않는다.
        assert session.get(CheckResult, result_id).invalidated_at is not None
        assert session.get(CaseApproval, approval_id).invalidated_at is not None
        assert session.get(PreparationCase, 1004).status == "준비 확인 완료"
        assert session.get(PreparationCase, 1005).status == "취소 완료"
        history = session.scalar(select(CaseHistory).where(CaseHistory.case_id == 1003,
                                                          CaseHistory.actor_id == "demo-officer"))
        assert history.from_status == "준비 확인 요청" and history.to_status == "준비중"


def test_office_scope_change_rechecks_only_affected_open_cases(client, factory, criterion):
    with factory.begin() as session:
        row = session.get(Criterion, criterion)
        row.office = "관서 A"
        session.get(PreparationCase, 1001).office = "관서 A"
        session.get(PreparationCase, 1002).office = "관서 B"
    response = client.post(f"/criteria/{criterion}", headers=OFFICER,
                           json={**BODY, "expected_version": 1, "office": "관서 A", "body": "관서 A 변경 기준"})
    assert response.status_code == 200
    assert response.json()["recheck_case_ids"] == [1001]
    with factory() as session:
        assert session.get(PreparationCase, 1002).status == "담당자 승인 대기"


def test_valid_inputs_are_automatically_rechecked_and_audited_as_system(client, factory, criterion):
    with factory.begin() as session:
        data = pdf_data()
        session.add(Attachment(case_id=1003, filename="mock.pdf", size_bytes=len(data), document_version=1, file_data=data))
    response = client.post(f"/criteria/{criterion}", headers=OFFICER,
                           json={**BODY, "expected_version": 1, "body": "재점검할 새 기준"})
    assert response.status_code == 200, response.text
    with factory() as session:
        assert session.get(PreparationCase, 1003).status == "담당자 승인 대기"
        result = session.scalar(select(CheckResult).where(CheckResult.case_id == 1003, CheckResult.invalidated_at.is_(None)))
        assert result.criterion_versions == [{"criterion_id": str(criterion), "version": 2}]
        history = session.scalar(select(CaseHistory).where(CaseHistory.case_id == 1003,
                                                          CaseHistory.to_status == "자동 점검중"))
        assert history.actor_role == "system"


def test_late_result_after_criterion_update_is_discarded(client, factory, criterion):
    entered, release = threading.Event(), threading.Event()
    class FirstSlow(MockTransport):
        first = True
        async def generate(self, payload):
            if self.first:
                self.first = False
                entered.set()
                import asyncio
                while not release.is_set():
                    await asyncio.sleep(0.01)
            return await super().generate(payload)
    with factory.begin() as session:
        data = pdf_data()
        session.add(Attachment(case_id=1003, filename="mock.pdf", size_bytes=len(data), document_version=1, file_data=data))
    client.app.state.check_transport = FirstSlow()
    try:
        with ThreadPoolExecutor() as pool:
            pending = pool.submit(client.post, "/cases/1003/check", headers=OWNER)
            try:
                assert entered.wait(5)
                changed = client.post(f"/criteria/{criterion}", headers=OFFICER,
                                      json={**BODY, "expected_version": 1, "body": "경합 뒤 새 기준"})
                assert changed.status_code == 200
            finally:
                release.set()
            assert pending.result(timeout=5).json()["discarded"] is True
        with factory() as session:
            results = session.scalars(select(CheckResult).where(CheckResult.case_id == 1003)).all()
            assert len(results) == 1
            assert results[0].criterion_versions == [{"criterion_id": str(criterion), "version": 2}]
    finally:
        del client.app.state.check_transport
