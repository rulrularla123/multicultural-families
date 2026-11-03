"""US-04 담당자가 분석 결과를 반려하기 — 인수 테스트.

기대값은 backlog.md US-04 인수 조건 원문에서만 가져온다. HTTP 코드는 인수 조건에 적힌 403만 확인하고,
나머지 거절은 "성공(2xx)이 아님 + 상태·이력 그대로"로 확인한다(API.md에 US-04 항목이 아직 없음).
이번에 다루지 않는 조건: 정상 2의 "수정해 다시 제출하면 재점검"(입력 수정·재점검 작업 뒤),
LLM 7 "반려 사유를 LLM에 보내지 않음"(LLM 클라이언트 작업 뒤).
시드: 1001 demo-user-1 담당자 승인 대기, 1003 준비중, 1004 준비 확인 완료, 1005 취소 완료.
"""
import pytest
from sqlalchemy import func, select

from app.models import CaseHistory, CaseStatus, PreparationCase


OFFICER = {"X-Demo-Account": "demo-officer"}
OWNER = {"X-Demo-Account": "demo-user-1"}
OTHER = {"X-Demo-Account": "demo-user-2"}
REASON = "추가 준비 서류 근거를 다시 확인해 주세요."


def state(factory, case_id=1001):
    with factory() as session:
        status = session.get(PreparationCase, case_id).status
        count = session.scalar(
            select(func.count()).select_from(CaseHistory).where(CaseHistory.case_id == case_id)
        )
        return status, count


def test_us04_officer_reject_with_reason_moves_to_preparing_and_records_history(client, factory):
    """US-04 (정상) 1: 사유 입력 반려 → 준비중, 반려자 ID·일시·사유가 이력에 기록."""
    response = client.post("/cases/1001/reject", headers=OFFICER, json={"reason": REASON})

    assert response.is_success
    with factory() as session:
        assert session.get(PreparationCase, 1001).status == CaseStatus.PREPARING.value
        history = session.scalars(select(CaseHistory).where(CaseHistory.case_id == 1001)).one()
        assert history.actor_id == "demo-officer"
        assert history.reason == REASON
        assert history.occurred_at is not None


def test_us04_one_character_reason_is_accepted(client, factory):
    """US-04 (정상) 1: 반려 사유는 1자 이상."""
    assert client.post("/cases/1001/reject", headers=OFFICER, json={"reason": "가"}).is_success
    assert state(factory)[0] == CaseStatus.PREPARING.value


def test_us04_owner_sees_rejection_reason_after_reject(client):
    """US-04 (정상) 2: 반려 후 이용자 화면에 반려 사유가 표시된다."""
    client.post("/cases/1001/reject", headers=OFFICER, json={"reason": REASON})

    response = client.get("/cases/1001", headers=OWNER)
    assert response.is_success
    assert REASON in response.text


@pytest.mark.parametrize("reason", ["", "   ", "\n"])
def test_us04_empty_reason_is_rejected_and_stays_waiting(client, factory, reason):
    """US-04 (실패·거절) 3: 사유가 비면 반려되지 않고 담당자 승인 대기 유지."""
    before = state(factory)

    assert not client.post("/cases/1001/reject", headers=OFFICER, json={"reason": reason}).is_success
    assert state(factory) == before == (CaseStatus.REVIEWING.value, 0)


@pytest.mark.parametrize("headers", [OWNER, OTHER], ids=["owner", "other-user"])
def test_us04_users_cannot_reject_403_and_state_unchanged(client, factory, headers):
    """US-04 (권한) 4: 이용자와 다른 이용자는 반려할 수 없다(403, 상태 불변)."""
    before = state(factory)

    response = client.post("/cases/1001/reject", headers=headers, json={"reason": REASON})
    assert response.status_code == 403
    assert state(factory) == before


def test_us04_other_user_cannot_see_rejection_reason(client):
    """US-04 (권한) 4: 반려 사유는 해당 건의 이용자와 담당자만 볼 수 있다."""
    client.post("/cases/1001/reject", headers=OFFICER, json={"reason": REASON})

    assert REASON in client.get("/cases/1001", headers=OFFICER).text
    assert REASON not in client.get("/cases/1001", headers=OTHER).text


@pytest.mark.parametrize("case_id", [1003, 1004, 1005], ids=["preparing", "completed", "canceled"])
def test_us04_reject_only_from_waiting_for_approval(client, factory, case_id):
    """US-04 (취소·반려) 5: 조건은 담당자 승인 대기 상태. 다른 상태는 바뀌지 않는다."""
    before = state(factory, case_id)

    assert not client.post(f"/cases/{case_id}/reject", headers=OFFICER, json={"reason": REASON}).is_success
    assert state(factory, case_id) == before


def test_us04_result_status_is_always_preparing(client):
    """US-04 (취소·반려) 5: 결과 상태는 항상 준비중."""
    client.post("/cases/1001/reject", headers=OFFICER, json={"reason": REASON})

    assert client.get("/cases/1001", headers=OWNER).json()["status"] == CaseStatus.PREPARING.value


def test_us04_rejected_analysis_is_not_shown_to_owner(client):
    """US-04 (LLM) 6: 반려된 분석 결과는 이용자에게 공개되지 않는다."""
    client.post("/cases/1001/reject", headers=OFFICER, json={"reason": REASON})

    assert "analysis_items" not in client.get("/cases/1001", headers=OWNER).json()
