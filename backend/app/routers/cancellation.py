from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, field_serializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dependencies import DemoActor, get_actor, get_session
from ..models import CaseHistory, CaseStatus, CheckResult, PreparationCase, utc_now


router = APIRouter()

CANCELABLE = {
    CaseStatus.PREPARING.value,
    CaseStatus.CHECKING.value,
    CaseStatus.REVIEWING.value,
    CaseStatus.COLLECTING.value,
    CaseStatus.REQUESTED.value,
    CaseStatus.SUPPLEMENT.value,
}


class CancelResponse(BaseModel):
    case_id: int
    status: CaseStatus
    previous_status: CaseStatus
    canceled_at: datetime

    @field_serializer("canceled_at")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


@router.post("/cases/{case_id}/cancel", response_model=CancelResponse)
def cancel_case(
    case_id: Annotated[int, Path(gt=0, le=18446744073709551615)],
    actor: Annotated[DemoActor, Depends(get_actor)],
    session: Annotated[Session, Depends(get_session)],
):
    with session.begin():
        case = session.scalar(
            select(PreparationCase).where(PreparationCase.id == case_id).with_for_update()
        )
        if case is None:
            raise HTTPException(404, "준비 건을 찾을 수 없습니다.")
        if actor.role != "user" or actor.id != case.owner_id:
            raise HTTPException(403, "본인의 준비 건만 취소할 수 있습니다.")
        if case.status not in CANCELABLE:
            raise HTTPException(409, "진행 중인 준비 건만 취소할 수 있습니다.")
        result = session.scalar(
            select(CheckResult).where(
                CheckResult.case_id == case_id,
                CheckResult.invalidated_at.is_(None),
            ).order_by(CheckResult.id.desc()).limit(1)
        )
        now = utc_now()
        previous = case.status
        # CaseHistory.reason이 필수 칸이라 사유 없는 취소는 빈 문자열로 둔다. 모델이 바뀌면 맞춘다.
        session.add(CaseHistory(
            case_id=case.id, from_status=previous, to_status=CaseStatus.CANCELED.value,
            actor_id=actor.id, actor_role=actor.role, reason="",
            criterion_versions=result.criterion_versions if result else [], occurred_at=now,
        ))
        case.status = CaseStatus.CANCELED.value
        # 점검 작업 연결을 끊어 취소 뒤 도착한 점검 결과가 저장되지 않게 한다.
        case.current_check_task_id = None
        session.flush()
        response = CancelResponse(
            case_id=case.id, status=case.status, previous_status=previous, canceled_at=now
        )
    return response
