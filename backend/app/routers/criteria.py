from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dependencies import DemoActor, get_session, require_officer
from ..models import Criterion


router = APIRouter()

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
Office = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128)]


class CriterionInput(BaseModel):
    """US-02 기준 등록: 공식 원문·출처·확인일은 필수다. office가 없으면 공통 기준이다."""
    model_config = ConfigDict(extra="forbid")

    office: Office | None = None
    body: Text
    source: Text
    checked_on: date
    is_verified: bool = False
    is_active: bool = True


class CriterionOut(BaseModel):
    id: int
    support_type: str
    office: str | None
    body: str
    source: str
    checked_on: date
    version: int
    is_verified: bool
    is_active: bool
    needs_office_check: bool


def out(criterion: Criterion) -> CriterionOut:
    return CriterionOut(
        id=criterion.id, support_type=criterion.support_type, office=criterion.office,
        body=criterion.body, source=criterion.source, checked_on=criterion.checked_on,
        version=criterion.version, is_verified=criterion.is_verified, is_active=criterion.is_active,
        # 관서별 기준인데 출처·최신 여부를 확인하지 않았으면 추가 요구를 만들지 않고 표시만 한다.
        needs_office_check=criterion.office is not None and not criterion.is_verified,
    )


@router.get("/criteria", response_model=list[CriterionOut])
def list_criteria(
    actor: Annotated[DemoActor, Depends(require_officer)],
    session: Annotated[Session, Depends(get_session)],
):
    rows = session.scalars(select(Criterion).order_by(Criterion.id))
    return [out(row) for row in rows]


@router.post("/criteria", response_model=CriterionOut, status_code=201)
def create_criterion(
    body: CriterionInput,
    actor: Annotated[DemoActor, Depends(require_officer)],
    session: Annotated[Session, Depends(get_session)],
):
    with session.begin():
        criterion = Criterion(support_type="F-6-1", version=1, **body.model_dump())
        session.add(criterion)
        session.flush()
        response = out(criterion)
    return response


# 변경은 같은 기준 ID의 version을 올린다. 점검·승인에 기록된 (기준 ID, 버전)과 달라지므로
# 이전 결과로는 승인·확인 요청·완료가 거절된다 (workflow.versions_match).
@router.post("/criteria/{criterion_id}", response_model=CriterionOut)
def update_criterion(
    criterion_id: Annotated[int, Path(gt=0, le=18446744073709551615)],
    body: CriterionInput,
    actor: Annotated[DemoActor, Depends(require_officer)],
    session: Annotated[Session, Depends(get_session)],
):
    with session.begin():
        criterion = session.scalar(select(Criterion).where(Criterion.id == criterion_id).with_for_update())
        if criterion is None:
            raise HTTPException(404, "기준을 찾을 수 없습니다.")
        for field, value in body.model_dump().items():
            setattr(criterion, field, value)
        criterion.version += 1
        session.flush()
        response = out(criterion)
    return response
