from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.main import create_app
from app.models import CaseHistory, CaseStatus, CheckResult, PreparationCase
from app.seed import seed_demo


OFFICER = {"X-Demo-Account": "demo-officer"}
OWNER = {"X-Demo-Account": "demo-user-1"}
OTHER = {"X-Demo-Account": "demo-user-2"}


def snapshot(factory):
    with factory() as session:
        case = session.get(PreparationCase, 1001)
        result = session.scalar(select(CheckResult).where(CheckResult.case_id == 1001))
        count = session.scalar(select(func.count()).select_from(CaseHistory))
        return case.status, result.invalidated_at, count


def test_us04_reject_records_actor_time_reason_and_invalidates_draft(client, factory):
    before = datetime.now(timezone.utc)
    response = client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "  누락 항목을 다시 확인해 주세요.  "})
    assert response.status_code == 200
    payload = response.json()
    assert payload["case_id"] == 1001
    assert payload["status"] == "준비중"
    assert payload["reason"] == "누락 항목을 다시 확인해 주세요."
    assert datetime.fromisoformat(payload["rejected_at"]) >= before
    with factory() as session:
        case = session.get(PreparationCase, 1001)
        history = session.scalar(select(CaseHistory))
        assert case.status == "준비중"
        assert case.current_check_task_id is None
        assert (history.from_status, history.to_status) == ("담당자 승인 대기", "준비중")
        assert (history.actor_id, history.actor_role) == ("demo-officer", "officer")
        assert history.reason == payload["reason"]
        assert history.occurred_at.replace(tzinfo=timezone.utc) == datetime.fromisoformat(payload["rejected_at"])
        assert session.scalar(select(CheckResult)).invalidated_at is not None


def test_us04_owner_sees_reason_but_never_rejected_analysis(client):
    before = client.get("/cases/1001", headers=OWNER)
    assert before.status_code == 200
    assert "analysis_items" not in before.json()
    officer_view = client.get("/cases/1001", headers=OFFICER)
    assert "공개하면 안 되는 모의 분석 초안" in officer_view.text
    assert client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "서류 수정"}).status_code == 200
    after = client.get("/cases/1001", headers=OWNER)
    assert after.json()["rejection_reason"] == "서류 수정"
    assert after.json()["status"] == "준비중"
    assert "공개하면 안 되는 모의 분석 초안" not in after.text
    assert "analysis_items" not in after.json()
    assert "demo-officer" not in after.text
    assert client.get("/cases/1001", headers=OTHER).status_code == 403


@pytest.mark.parametrize("body", [
    {}, {"reason": ""}, {"reason": " \n\t　"}, {"reason": None},
    {"reason": 1}, {"reason": True}, {"reason": []},
    {"reason": "수정", "status": "준비 확인 완료"},
    {"reason": "수정", "actor_id": "demo-officer"},
])
def test_us04_invalid_reason_or_forged_fields_do_not_change_data(client, factory, body):
    before = snapshot(factory)
    response = client.post("/cases/1001/reject", headers=OFFICER, json=body)
    assert response.status_code == 422
    assert snapshot(factory) == before


@pytest.mark.parametrize("headers,status", [({}, 401), ({"X-Demo-Account": "unknown"}, 401), (OWNER, 403), (OTHER, 403), ({**OWNER, "X-Role": "officer"}, 403)])
def test_us04_only_known_officer_can_reject(client, factory, headers, status):
    before = snapshot(factory)
    response = client.post("/cases/1001/reject", headers=headers, json={"reason": "수정"})
    assert response.status_code == status
    assert snapshot(factory) == before


@pytest.mark.parametrize("status", [s for s in CaseStatus if s != CaseStatus.REVIEWING])
def test_us04_reject_only_from_approval_waiting(client, factory, status):
    with factory.begin() as session:
        session.get(PreparationCase, 1001).status = status.value
    before = snapshot(factory)
    response = client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "수정"})
    assert response.status_code == 409
    assert snapshot(factory) == before


def test_us04_one_character_reason_is_accepted(client):
    assert client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "가"}).status_code == 200


def test_us04_missing_case_does_not_create_history(client, factory):
    before = snapshot(factory)
    assert client.post("/cases/999999/reject", headers=OFFICER, json={"reason": "수정"}).status_code == 404
    assert client.get("/cases/999999", headers=OFFICER).status_code == 404
    assert snapshot(factory) == before


@pytest.mark.parametrize("headers", [{}, {"X-Demo-Account": "unknown"}])
def test_us04_anonymous_cannot_read_reason_or_draft(client, headers):
    assert client.get("/cases/1001", headers=headers).status_code == 401


def test_us04_audit_failure_rolls_back_state_and_result(engine, factory):
    before = snapshot(factory)

    def reject_history_write(session, flush_context, instances):
        if any(isinstance(item, CaseHistory) for item in session.new):
            raise RuntimeError("이력 저장 실패 모의 시험")

    event.listen(factory, "before_flush", reject_history_write)
    try:
        with TestClient(create_app(engine=engine, demo_mode=True), raise_server_exceptions=False) as client:
            client.app.state.session_factory = factory
            response = client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "수정"})
        assert response.status_code == 500
    finally:
        event.remove(factory, "before_flush", reject_history_write)
    assert snapshot(factory) == before


def test_us04_concurrent_rejections_create_exactly_one_history(engine, factory):
    with TestClient(create_app(engine=engine, demo_mode=True)) as first, TestClient(create_app(engine=engine, demo_mode=True)) as second:
        def send(client):
            return client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "동시 반려"}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(send, [first, second]))
    assert sorted(statuses) == [200, 409]
    assert snapshot(factory)[0] == "준비중"
    assert snapshot(factory)[2] == 1


def test_us04_repeat_request_does_not_duplicate_history(client, factory):
    assert client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "수정"}).status_code == 200
    before = snapshot(factory)
    assert client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "수정"}).status_code == 409
    assert snapshot(factory) == before


def test_seed_has_five_cases_and_does_not_reset_rejected_case(client, factory):
    client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "수정"})
    with factory.begin() as session:
        assert seed_demo(session, "test-language") == 0
        assert session.scalar(select(func.count()).select_from(PreparationCase)) == 5
        assert session.get(PreparationCase, 1001).status == "준비중"


def test_status_values_match_selected_topic_b():
    source = Path(__file__).resolve().parents[2] / "docs/domain/03-rules-states-llm.md"
    section = source.read_text().split("### 선정 주제 B의 상태 흐름", 1)[1].split("## 3-3.", 1)[0]
    assert [s.value for s in CaseStatus] == re.findall(r'state "([^"]+)" as ', section)


def test_demo_auth_is_not_silently_enabled(engine):
    with pytest.raises(RuntimeError, match="DEMO_MODE"):
        with TestClient(create_app(engine=engine, demo_mode=False)):
            pass


def test_us04_history_preserves_criterion_version_snapshot(client, factory):
    versions = [{"criterion_id": 77, "version": 2}]
    with factory.begin() as session:
        session.scalar(select(CheckResult).where(CheckResult.case_id == 1001)).criterion_versions = versions
    response = client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "근거 재확인"})
    assert response.status_code == 200
    with factory() as session:
        assert session.scalar(select(CaseHistory)).criterion_versions == versions


@pytest.mark.parametrize("case_id", [0, -1, 18446744073709551616, "invalid"])
def test_us04_invalid_case_id_is_rejected_before_database_access(client, factory, case_id):
    before = snapshot(factory)
    assert client.get(f"/cases/{case_id}", headers=OFFICER).status_code == 422
    assert client.post(f"/cases/{case_id}/reject", headers=OFFICER, json={"reason": "수정"}).status_code == 422
    assert snapshot(factory) == before


def test_us04_criteria_recheck_history_is_not_a_rejection_reason(client, factory):
    """US-04 반려 사유 조회: 기준 변경으로 준비중에 돌아간 이력은 반려가 아니다."""
    from app.dependencies import DemoActor
    from app.workflow import history

    with factory.begin() as session:
        case = session.get(PreparationCase, 1001)
        history(session, case, DemoActor("demo-officer", "officer"), CaseStatus.PREPARING,
                reason="기준 버전 변경으로 이전 결과를 무효화하고 재점검")
    response = client.get("/cases/1001", headers=OWNER)
    assert response.status_code == 200
    assert response.json()["status"] == "준비중"
    assert response.json()["rejection_reason"] is None


def test_us04_actual_rejection_reason_survives_later_recheck_history(client, factory):
    """US-04: 마지막 실제 반려 사유를 재점검 시스템 이력으로 덮어쓰지 않는다."""
    from app.dependencies import DemoActor
    from app.workflow import history

    assert client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "모의 서류를 수정하세요"}).status_code == 200
    with factory.begin() as session:
        case = session.get(PreparationCase, 1001)
        history(session, case, DemoActor("demo-officer", "officer"), CaseStatus.PREPARING,
                reason="기준 버전 변경으로 재점검")
    assert client.get("/cases/1001", headers=OWNER).json()["rejection_reason"] == "모의 서류를 수정하세요"


def test_us04_legacy_rejection_without_action_remains_visible(client, factory):
    """기존 모의 DB의 action=NULL 반려 이력도 사유를 보존한다."""
    assert client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "이전 반려 사유"}).status_code == 200
    with factory.begin() as session:
        session.scalar(select(CaseHistory).where(CaseHistory.case_id == 1001)).action = None
    assert client.get("/cases/1001", headers=OWNER).json()["rejection_reason"] == "이전 반려 사유"


def test_us04_action_schema_upgrade_preserves_legacy_history(engine, client, factory):
    """기존 DB 이력에 구분 필드를 추가해도 원문·조회 결과를 유지한다."""
    from sqlalchemy import text
    from app.database import prepare_workflow_schema

    assert client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "보존할 반려 사유"}).status_code == 200
    try:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE case_histories DROP COLUMN action"))
        assert prepare_workflow_schema(engine) == ["case_histories.action 추가"]
        assert prepare_workflow_schema(engine) == []
        assert client.get("/cases/1001", headers=OWNER).json()["rejection_reason"] == "보존할 반려 사유"
    finally:
        prepare_workflow_schema(engine)
