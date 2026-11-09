from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..dependencies import DemoActor, get_session, require_officer
from ..models import CaseHistory, CaseStatus, CheckResult, PreparationCase, utc_now
from ..schemas import RejectRequest, RejectResponse


router = APIRouter()


@router.post("/cases/{case_id}/reject", response_model=RejectResponse)
def reject_case(
    case_id: Annotated[int, Path(gt=0, le=18446744073709551615)],
    body: RejectRequest,
    actor: Annotated[DemoActor, Depends(require_officer)],
    session: Annotated[Session, Depends(get_session)],
):
    with session.begin():
        case = session.scalar(
            select(PreparationCase).where(PreparationCase.id == case_id).with_for_update()
        )
        if case is None:
            raise HTTPException(404, "준비 건을 찾을 수 없습니다.")
        if case.status != CaseStatus.REVIEWING.value:
            raise HTTPException(409, "담당자 승인 대기 상태에서만 반려할 수 있습니다.")
        result = session.scalar(
            select(CheckResult).where(
                CheckResult.case_id == case_id,
                CheckResult.invalidated_at.is_(None),
            ).order_by(CheckResult.id.desc()).limit(1)
        )
        now = utc_now()
        history = CaseHistory(
            case_id=case.id, from_status=case.status, to_status=CaseStatus.PREPARING.value,
            actor_id=actor.id, actor_role=actor.role, reason=body.reason, action="rejection",
            criterion_versions=result.criterion_versions if result else [], occurred_at=now,
        )
        case.status = CaseStatus.PREPARING.value
        case.current_check_task_id = None
        session.execute(
            update(CheckResult).where(
                CheckResult.case_id == case_id, CheckResult.invalidated_at.is_(None)
            ).values(invalidated_at=now)
        )
        session.add(history)
        session.flush()
        response = RejectResponse(case_id=case.id, status=case.status, reason=body.reason, rejected_at=now)
    return response
