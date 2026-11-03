"""US-08 이용자가 진행 중인 준비 건 취소하기. 인수 조건은 backlog.md US-08 원문 기준."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import create_app
from app.models import CaseHistory, CaseStatus, PreparationCase
from app.routers import cancellation


OFFICER = {"X-Demo-Account": "demo-officer"}
OWNER = {"X-Demo-Account": "demo-user-1"}
OTHER = {"X-Demo-Account": "demo-user-2"}

IN_PROGRESS = [
    CaseStatus.PREPARING,
    CaseStatus.CHECKING,
    CaseStatus.REVIEWING,
    CaseStatus.COLLECTING,
    CaseStatus.REQUESTED,
    CaseStatus.SUPPLEMENT,
]


@pytest.fixture
def cancel_client(engine, factory):
    # main.py에 취소 router가 연결되기 전까지 테스트 앱에만 붙인다.
    app = create_app(engine=engine, demo_mode=True)
    if not any(getattr(route, "path", "") == "/cases/{case_id}/cancel" for route in app.routes):
        app.include_router(cancellation.router)
    with TestClient(app) as client:
        yield client


def set_status(factory, case_id, status, task_id=None):
    with factory.begin() as session:
        case = session.get(PreparationCase, case_id)
        case.status = status.value
        case.current_check_task_id = task_id


def snapshot(factory, case_id):
    with factory() as session:
        case = session.get(PreparationCase, case_id)
        count = session.scalar(select(func.count()).select_from(CaseHistory))
        return case.status, count


@pytest.mark.parametrize("status", IN_PROGRESS)
def test_us08_owner_cancels_in_progress_case_and_history_is_recorded(cancel_client, factory, status):
    set_status(factory, 1003, status)
    before = datetime.now(timezone.utc)

    response = cancel_client.post("/cases/1003/cancel", headers=OWNER)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "취소 완료"
    assert payload["previous_status"] == status.value
    assert datetime.fromisoformat(payload["canceled_at"]) >= before
    with factory() as session:
        assert session.get(PreparationCase, 1003).status == "취소 완료"
        history = session.scalar(select(CaseHistory).where(CaseHistory.case_id == 1003))
        assert (history.from_status, history.to_status) == (status.value, "취소 완료")
        assert (history.actor_id, history.actor_role) == ("demo-user-1", "user")
        assert history.occurred_at.replace(tzinfo=timezone.utc) == datetime.fromisoformat(payload["canceled_at"])


def test_us08_cancel_during_check_detaches_check_task(cancel_client, factory):
    set_status(factory, 1003, CaseStatus.CHECKING, task_id="task-before-cancel")

    assert cancel_client.post("/cases/1003/cancel", headers=OWNER).status_code == 200

    with factory() as session:
        case = session.get(PreparationCase, 1003)
        assert case.status == "취소 완료"
        assert case.current_check_task_id is None


@pytest.mark.parametrize("case_id", [1004, 1005])
def test_us08_finished_case_cannot_be_canceled(cancel_client, factory, case_id):
    before = snapshot(factory, case_id)

    assert cancel_client.post(f"/cases/{case_id}/cancel", headers=OWNER).status_code == 409
    assert snapshot(factory, case_id) == before


@pytest.mark.parametrize(
    "headers, status",
    [({}, 401), ({"X-Demo-Account": "unknown"}, 401), (OTHER, 403), (OFFICER, 403)],
)
def test_us08_only_owner_can_cancel(cancel_client, factory, headers, status):
    before = snapshot(factory, 1003)

    assert cancel_client.post("/cases/1003/cancel", headers=headers).status_code == status
    assert snapshot(factory, 1003) == before


def test_us08_missing_case_returns_404(cancel_client):
    assert cancel_client.post("/cases/9999/cancel", headers=OWNER).status_code == 404


def test_us08_canceled_case_cannot_be_rejected(cancel_client, factory):
    assert cancel_client.post("/cases/1001/cancel", headers=OWNER).status_code == 200

    response = cancel_client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "수정"})

    assert response.status_code == 409
    assert snapshot(factory, 1001)[0] == "취소 완료"
