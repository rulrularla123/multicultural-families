"""US-06: 승인 항목 보완·수정 시작·재요청·해소 확인 및 US-07 완료 연결."""
import json

import pytest
from sqlalchemy import event, func, select

from app.models import CaseApproval, CaseHistory, CheckResult, Criterion, PreparationCase, PreparationItem
from app.supplement_seed import DEMO_CASE_ID, seed_supplement_case


PATH = f"/cases/{DEMO_CASE_ID}"
OFFICER = {"X-Demo-Account": "demo-officer"}
OWNER = {"X-Demo-Account": "demo-user-1"}
OTHER = {"X-Demo-Account": "demo-user-2"}
NOTICE = "Đây không phải là xác nhận tiếp nhận hồ sơ hoặc cấp phép gia hạn lưu trú."


@pytest.fixture
def ready(factory, client):
    with factory.begin() as session:
        assert seed_supplement_case(session) == 1
    response = client.get(f"{PATH}/supplement", headers=OFFICER)
    assert response.status_code == 200, response.text
    return response.json()


def request_body(ready):
    return {"approval_id": ready["approval_id"], "items": [{"id": ready["items"][0]["id"], "reason": "모의 자료의 빠진 부분을 확인해 주세요."}]}


def snapshot(factory):
    with factory() as session:
        case = session.get(PreparationCase, DEMO_CASE_ID)
        items = session.scalars(select(PreparationItem).where(PreparationItem.case_id == DEMO_CASE_ID)
                                .order_by(PreparationItem.id)).all()
        return (case.status, [(i.prepared, i.supplement_reason, i.supplement_resolved) for i in items],
                session.scalar(select(func.count()).select_from(CaseHistory)))


def start(client, ready):
    assert client.post(f"{PATH}/supplement", headers=OFFICER, json=request_body(ready)).status_code == 200
    response = client.post(f"{PATH}/start-revision", headers=OWNER, json={"approval_id": ready["approval_id"]})
    assert response.status_code == 200, response.text
    return response.json()


def test_supplement_cycle_requires_officer_resolution_before_completion(client, factory, ready):
    body = request_body(ready)
    requested = client.post(f"{PATH}/supplement", headers=OFFICER, json=body)
    assert requested.status_code == 200, requested.text
    assert requested.json()["status"] == "보완 요청"
    owner = client.get(f"{PATH}/supplement", headers=OWNER).json()
    assert owner["can_restart"] is True
    assert owner["items"][0]["supplement_reason"] == body["items"][0]["reason"]
    assert owner["items"][0]["supplement_resolved"] is False
    restarted = client.post(f"{PATH}/start-revision", headers=OWNER, json={"approval_id": ready["approval_id"]}).json()
    assert restarted["status"] == "서류 준비중"
    assert restarted["items"][0]["prepared"] is False
    assert restarted["items"][1]["prepared"] is True
    item_id = ready["items"][0]["id"]
    assert client.post(f"{PATH}/preparation-items", headers=OWNER, json={"items": [{"id": item_id, "prepared": True}]}).status_code == 200
    assert client.post(f"{PATH}/request-confirmation", headers=OWNER).status_code == 200
    notice = {"notice_translation": NOTICE, "translation_confirmed": True}
    assert client.post(f"{PATH}/complete", headers=OFFICER, json=notice).status_code == 409
    resolved = client.post(f"{PATH}/resolve-supplements", headers=OFFICER,
                           json={"approval_id": ready["approval_id"], "item_ids": [item_id], "reason": "모의 보완 자료 확인"})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "준비 확인 요청"
    assert resolved.json()["items"][0]["supplement_resolved"] is True
    completed = client.post(f"{PATH}/complete", headers=OFFICER, json=notice)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "준비 확인 완료"
    with factory() as session:
        history = session.scalars(select(CaseHistory).where(CaseHistory.case_id == DEMO_CASE_ID)
                                  .order_by(CaseHistory.id)).all()
        assert json.loads(history[0].reason)["items"] == body["items"]
        assert history[0].actor_role == "officer" and history[1].actor_role == "user"
        assert history[0].criterion_versions == history[-1].criterion_versions


@pytest.mark.parametrize("headers,expected", [({}, 401), (OTHER, 403), (OWNER, 200), (OFFICER, 200)])
def test_only_owner_and_officer_read_approved_supplement_items(client, ready, headers, expected):
    assert client.get(f"{PATH}/supplement", headers=headers).status_code == expected


@pytest.mark.parametrize("suffix,headers,expected", [
    ("supplement", OWNER, 403), ("supplement", OTHER, 403), ("supplement", {}, 401),
    ("start-revision", OFFICER, 403), ("start-revision", OTHER, 403), ("start-revision", {}, 401),
    ("resolve-supplements", OWNER, 403), ("resolve-supplements", OTHER, 403), ("resolve-supplements", {}, 401),
])
def test_mutation_roles_are_enforced_without_changes(client, factory, ready, suffix, headers, expected):
    body = request_body(ready) if suffix == "supplement" else {"approval_id": ready["approval_id"]}
    if suffix == "resolve-supplements":
        body.update(item_ids=[ready["items"][0]["id"]], reason="확인")
    before = snapshot(factory)
    assert client.post(f"{PATH}/{suffix}", headers=headers, json=body).status_code == expected
    assert snapshot(factory) == before


@pytest.mark.parametrize("kind", ["empty", "blank_reason", "missing_reason", "duplicate", "unknown", "wrong_type", "extra"])
def test_invalid_request_preserves_status_and_all_items(client, factory, ready, kind):
    body = request_body(ready)
    if kind == "empty": body["items"] = []
    if kind == "blank_reason": body["items"][0]["reason"] = "  "
    if kind == "missing_reason": del body["items"][0]["reason"]
    if kind == "duplicate": body["items"] *= 2
    if kind == "unknown": body["items"][0]["id"] = 999999
    if kind == "wrong_type": body["items"][0]["id"] = str(body["items"][0]["id"])
    if kind == "extra": body["status"] = "준비 확인 완료"
    before = snapshot(factory)
    assert client.post(f"{PATH}/supplement", headers=OFFICER, json=body).status_code == 422
    assert snapshot(factory) == before


@pytest.mark.parametrize("status", ["준비중", "자동 점검중", "담당자 승인 대기", "서류 준비중", "보완 요청", "준비 확인 완료", "취소 완료"])
def test_supplement_request_requires_confirmation_requested_status(client, factory, ready, status):
    with factory.begin() as session:
        session.get(PreparationCase, DEMO_CASE_ID).status = status
    before = snapshot(factory)
    assert client.post(f"{PATH}/supplement", headers=OFFICER, json=request_body(ready)).status_code == 409
    assert snapshot(factory) == before


@pytest.mark.parametrize("status", ["준비 확인 완료", "취소 완료"])
def test_finished_cases_reject_restart_and_resolution(client, factory, ready, status):
    with factory.begin() as session:
        session.get(PreparationCase, DEMO_CASE_ID).status = status
    before = snapshot(factory)
    assert client.post(f"{PATH}/start-revision", headers=OWNER, json={"approval_id": ready["approval_id"]}).status_code == 409
    assert client.post(f"{PATH}/resolve-supplements", headers=OFFICER,
                       json={"approval_id": ready["approval_id"], "item_ids": [ready["items"][0]["id"]], "reason": "확인"}).status_code == 409
    assert snapshot(factory) == before


@pytest.mark.parametrize("change", ["approval", "situation", "document", "criterion"])
def test_stale_approval_or_versions_reject_supplement_request(client, factory, ready, change):
    body = request_body(ready)
    if change == "approval": body["approval_id"] += 999
    else:
        with factory.begin() as session:
            case = session.get(PreparationCase, DEMO_CASE_ID)
            if change == "situation": case.situation_version += 1
            if change == "document": case.document_version += 1
            if change == "criterion": session.scalar(select(Criterion)).version += 1
    before = snapshot(factory)
    assert client.post(f"{PATH}/supplement", headers=OFFICER, json=body).status_code == 409
    assert snapshot(factory) == before


def test_marking_prepared_does_not_resolve_supplement_and_repeated_restart_is_rejected(client, factory, ready):
    start(client, ready)
    assert client.post(f"{PATH}/start-revision", headers=OWNER, json={"approval_id": ready["approval_id"]}).status_code == 409
    assert client.post(f"{PATH}/preparation-items", headers=OWNER,
                       json={"items": [{"id": ready["items"][0]["id"], "prepared": True}]}).status_code == 200
    assert client.get(f"{PATH}/supplement", headers=OWNER).json()["items"][0]["supplement_resolved"] is False


def test_officer_cannot_resolve_unprepared_item(client, factory, ready):
    start(client, ready)
    assert client.post(f"{PATH}/request-confirmation", headers=OWNER).status_code == 200
    before = snapshot(factory)
    assert client.post(f"{PATH}/resolve-supplements", headers=OFFICER,
                       json={"approval_id": ready["approval_id"], "item_ids": [ready["items"][0]["id"]], "reason": "확인"}).status_code == 409
    assert snapshot(factory) == before


def test_history_failure_rolls_back_supplement_request(client, factory, ready):
    before = snapshot(factory)
    def fail(session, context, instances):
        if any(isinstance(row, CaseHistory) for row in session.new): raise RuntimeError("mock history write failure")
    actual_session = client.app.state.session_factory.class_
    event.listen(actual_session, "before_flush", fail)
    try:
        with pytest.raises(RuntimeError, match="mock history write failure"):
            client.post(f"{PATH}/supplement", headers=OFFICER, json=request_body(ready))
    finally:
        event.remove(actual_session, "before_flush", fail)
    assert snapshot(factory) == before


def test_seed_is_idempotent_and_preserves_existing_case(factory):
    with factory.begin() as session:
        assert seed_supplement_case(session) == 1
        session.get(PreparationCase, DEMO_CASE_ID).situation = "수정한 모의 상황"
    with factory.begin() as session:
        assert seed_supplement_case(session) == 0
        assert session.get(PreparationCase, DEMO_CASE_ID).situation == "수정한 모의 상황"
