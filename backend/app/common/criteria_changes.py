"""F-02 변경과 US-02 재점검 연결. API 입력·출력 계약은 criteria router가 유지한다."""
from fastapi import HTTPException
from sqlalchemy import select, update

from .. import workflow as flow
from ..dependencies import DemoActor
from ..models import CaseApproval, CaseStatus, CheckResult, Criterion, PreparationCase, utc_now


FINISHED = (CaseStatus.COMPLETED.value, CaseStatus.CANCELED.value)
SYSTEM_ACTOR = DemoActor("system:criteria-recheck", "system")


def applied_versions(criteria, case):
    return [{"criterion_id": str(c.id), "version": c.version} for c in criteria
            if c.is_active and (c.office is None or c.office == case.office)]


def lock_scope(session):
    cases = session.scalars(select(PreparationCase).where(
        PreparationCase.support_type == "F-6-1", PreparationCase.status.not_in(FINISHED),
    ).order_by(PreparationCase.id).with_for_update()).all()
    criteria = session.scalars(select(Criterion).where(Criterion.support_type == "F-6-1")
                              .order_by(Criterion.id).with_for_update()).all()
    before = {case.id: applied_versions(criteria, case) for case in cases}
    return cases, criteria, before


def invalidate_changed_cases(session, cases, criteria, before, actor, criterion):
    changed, now = [], utc_now()
    for case in cases:
        if before[case.id] == applied_versions(criteria, case):
            continue
        session.execute(update(CheckResult).where(
            CheckResult.case_id == case.id, CheckResult.invalidated_at.is_(None),
        ).values(invalidated_at=now))
        session.execute(update(CaseApproval).where(
            CaseApproval.case_id == case.id, CaseApproval.invalidated_at.is_(None),
        ).values(invalidated_at=now))
        case.current_check_task_id = None
        flow.history(session, case, actor, CaseStatus.PREPARING,
                     reason=f"기준 {criterion.id} 버전 {criterion.version} 반영: 이전 결과·확인 요청 무효화 후 재점검",
                     criterion_versions=before[case.id])
        changed.append(case.id)
    return changed


async def recheck_cases(factory, case_ids, transport):
    for case_id in case_ids:
        with factory() as session:
            case = session.get(PreparationCase, case_id)
            if case is None or case.status != CaseStatus.PREPARING.value:
                continue
            owner = DemoActor(case.owner_id, "user")
        try:
            await flow.perform_check(factory, case_id, owner, transport, audit_actor=SYSTEM_ACTOR)
        except HTTPException as error:
            # 미확인 기준·자료 오류는 이전 결과를 공개하지 않고 준비중을 유지한다.
            if error.status_code == 422:
                with factory.begin() as session:
                    current = flow.locked_case(session, case_id)
                    if current.status == CaseStatus.PREPARING.value and current.current_check_task_id is None:
                        flow.history(session, current, SYSTEM_ACTOR, CaseStatus.PREPARING,
                                     "기준 변경 후 재점검 입력 검사를 통과하지 못했습니다. 모의 자료를 확인하세요.")
