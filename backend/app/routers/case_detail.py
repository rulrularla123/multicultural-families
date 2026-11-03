from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dependencies import DemoActor, get_actor, get_session
from ..models import CaseHistory, CaseStatus, CheckResult, PreparationCase
from ..schemas import CaseDetail, OfficerCaseDetail


router = APIRouter()


@router.get("/cases/{case_id}")
def case_detail(
    case_id: Annotated[int, Path(gt=0, le=18446744073709551615)],
    actor: Annotated[DemoActor, Depends(get_actor)],
    session: Annotated[Session, Depends(get_session)],
):
    case = session.get(PreparationCase, case_id)
    if case is None:
        raise HTTPException(404, "준비 건을 찾을 수 없습니다.")
    if actor.role != "officer" and actor.id != case.owner_id:
        raise HTTPException(403, "본인의 준비 건만 볼 수 있습니다.")
    latest_rejection = session.scalar(
        select(CaseHistory)
        .where(CaseHistory.case_id == case_id, CaseHistory.to_status == CaseStatus.PREPARING.value)
        .order_by(CaseHistory.id.desc()).limit(1)
    )
    payload = dict(
        id=case.id, situation=case.situation, display_language=case.display_language,
        support_type=case.support_type, status=case.status,
        rejection_reason=latest_rejection.reason if latest_rejection else None,
    )
    if actor.role == "officer" and case.status == CaseStatus.REVIEWING.value:
        result = session.scalar(
            select(CheckResult).where(
                CheckResult.case_id == case_id,
                CheckResult.invalidated_at.is_(None),
            ).order_by(CheckResult.id.desc()).limit(1)
        )
        return OfficerCaseDetail(**payload, analysis_items=result.analysis_items if result else []).model_dump(mode="json")
    # 이용자에게는 분석 본문과 담당자 계정 ID를 직렬화하지 않는다.
    return CaseDetail(**payload).model_dump(mode="json")
