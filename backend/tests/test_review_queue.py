"""F-09 검토 대기 목록 (US-02 (정상) 4: 담당자 부재 중 점검이 끝난 건도 담당자가 찾을 수 있다)."""

import pytest

from app.models import CaseStatus, CheckResult, PreparationCase


OFFICER = {"X-Demo-Account": "demo-officer"}
OWNER = {"X-Demo-Account": "demo-user-1"}


def test_queue_lists_only_reviewing_and_requested_cases_oldest_first(client, factory):
    with factory.begin() as session:
        session.get(PreparationCase, 1003).status = CaseStatus.REQUESTED.value

    response = client.get("/review-queue", headers=OFFICER)

    assert response.status_code == 200
    items = response.json()
    assert {item["id"] for item in items} == {1001, 1002, 1003}
    assert all(item["status"] in ("담당자 승인 대기", "준비 확인 요청") for item in items)
    created = [item["created_at"] for item in items]
    assert created == sorted(created)
    assert set(items[0]) == {"id", "support_type", "status", "created_at", "failure_reason"}


def test_queue_shows_failure_reason_of_current_check_only(client, factory):
    with factory.begin() as session:
        current = session.query(CheckResult).filter(CheckResult.case_id == 1001).one()
        current.failure_reason = "llm_timeout"

    items = {item["id"]: item for item in client.get("/review-queue", headers=OFFICER).json()}

    assert items[1001]["failure_reason"] == "llm_timeout"
    assert items[1002]["failure_reason"] is None


def test_queue_hides_invalidated_failure(client, factory):
    from app.models import utc_now
    with factory.begin() as session:
        result = session.query(CheckResult).filter(CheckResult.case_id == 1001).one()
        result.failure_reason = "llm_timeout"
        result.invalidated_at = utc_now()

    items = {item["id"]: item for item in client.get("/review-queue", headers=OFFICER).json()}

    assert items[1001]["failure_reason"] is None


def test_queue_does_not_include_analysis_or_situation(client):
    body = client.get("/review-queue", headers=OFFICER).text

    assert "공개하면 안 되는 모의 분석 초안" not in body
    assert "체류기간 연장을 위해" not in body


@pytest.mark.parametrize("headers, status", [({}, 401), ({"X-Demo-Account": "unknown"}, 401), (OWNER, 403)])
def test_queue_is_officer_only(client, headers, status):
    assert client.get("/review-queue", headers=headers).status_code == status
