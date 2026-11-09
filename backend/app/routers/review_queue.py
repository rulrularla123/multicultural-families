from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_serializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dependencies import DemoActor, get_session, require_officer
from ..models import CaseStatus, CheckResult, PreparationCase


router = APIRouter()

# DESIGN.md 검토 대기 목록 (F-09): 담당자가 처리할 두 상태만 보인다.
QUEUE_STATES = (CaseStatus.REVIEWING.value, CaseStatus.REQUESTED.value)


class QueueItem(BaseModel):
    id: int
    support_type: str
    status: CaseStatus
    created_at: datetime
    failure_reason: str | None

    @field_serializer("created_at")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


@router.get("/review-queue", response_model=list[QueueItem])
def review_queue(
    actor: Annotated[DemoActor, Depends(require_officer)],
    session: Annotated[Session, Depends(get_session)],
):
    cases = session.scalars(
        select(PreparationCase).where(PreparationCase.status.in_(QUEUE_STATES))
        .order_by(PreparationCase.created_at.asc(), PreparationCase.id.asc())
    ).all()
    items = []
    for case in cases:
        failure = None
        if case.status == CaseStatus.REVIEWING.value:
            # 담당자 부재 중 끝난 점검도 여기서 보인다. 실패면 "자동 점검 실패"로 표시하게 사유를 싣는다.
            failure = session.scalar(
                select(CheckResult.failure_reason).where(
                    CheckResult.case_id == case.id, CheckResult.invalidated_at.is_(None),
                ).order_by(CheckResult.id.desc()).limit(1)
            )
        items.append(QueueItem(
            id=case.id, support_type=case.support_type, status=case.status,
            created_at=case.created_at, failure_reason=failure,
        ))
    return items
