from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dependencies import DemoActor, get_session, require_officer
from ..common.criteria_changes import invalidate_changed_cases, lock_scope, recheck_cases
from ..common.llm_client import MockTransport
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


class CriterionChange(CriterionOut):
    recheck_case_ids: list[int]


class CriterionUpdate(CriterionInput):
    # 기존 요청과 호환한다. 관리 화면은 읽었던 버전을 보내 덮어쓰기를 막는다.
    expected_version: int | None = Field(default=None, strict=True, ge=1, le=4294967295)


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


@router.post("/criteria", response_model=CriterionChange, status_code=201)
def create_criterion(
    body: CriterionInput,
    actor: Annotated[DemoActor, Depends(require_officer)],
    session: Annotated[Session, Depends(get_session)],
    request: Request,
    background_tasks: BackgroundTasks,
):
    with session.begin():
        cases, criteria, before = lock_scope(session)
        criterion = Criterion(support_type="F-6-1", version=1, **body.model_dump())
        session.add(criterion)
        session.flush()
        criteria.append(criterion)
        changed = invalidate_changed_cases(session, cases, criteria, before, actor, criterion)
        response = CriterionChange(**out(criterion).model_dump(), recheck_case_ids=changed)
    background_tasks.add_task(recheck_cases, request.app.state.session_factory, changed,
                              getattr(request.app.state, "check_transport", None) or MockTransport())
    return response


@router.post("/criteria/{criterion_id}", response_model=CriterionChange)
def update_criterion(
    criterion_id: Annotated[int, Path(gt=0, le=18446744073709551615)],
    body: CriterionUpdate,
    actor: Annotated[DemoActor, Depends(require_officer)],
    session: Annotated[Session, Depends(get_session)],
    request: Request,
    background_tasks: BackgroundTasks,
):
    with session.begin():
        cases, criteria, before = lock_scope(session)
        criterion = next((c for c in criteria if c.id == criterion_id), None)
        if criterion is None:
            raise HTTPException(404, "기준을 찾을 수 없습니다.")
        if body.expected_version is not None and criterion.version != body.expected_version:
            raise HTTPException(409, "다른 담당자가 기준을 변경했습니다. 최신 기준을 다시 불러오세요.")
        values = body.model_dump(exclude={"expected_version"})
        if any(getattr(criterion, key) != value for key, value in values.items()):
            if criterion.version >= 4294967295:
                raise HTTPException(409, "기준 버전의 범위를 초과했습니다.")
            for field, value in values.items():
                setattr(criterion, field, value)
            criterion.version += 1
        changed = invalidate_changed_cases(session, cases, criteria, before, actor, criterion)
        session.flush()
        response = CriterionChange(**out(criterion).model_dump(), recheck_case_ids=changed)
    background_tasks.add_task(recheck_cases, request.app.state.session_factory, changed,
                              getattr(request.app.state, "check_transport", None) or MockTransport())
    return response
