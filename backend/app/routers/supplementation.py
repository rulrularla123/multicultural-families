"""US-06 보완 요청·수정 시작·담당자 해소 확인. 승인된 현재 준비 항목만 변경한다."""
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from .. import workflow as flow
from ..dependencies import DemoActor, get_actor, get_session
from ..models import CaseStatus


router = APIRouter()
Actor = Annotated[DemoActor, Depends(get_actor)]
DB = Annotated[Session, Depends(get_session)]
CaseID = Annotated[int, Path(gt=0, le=18446744073709551615)]
ItemID = Annotated[int, Field(strict=True, gt=0, le=18446744073709551615)]
Reason = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=10000)]


class CurrentApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approval_id: ItemID


class SupplementItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: ItemID
    reason: Reason


class SupplementRequest(CurrentApproval):
    items: list[SupplementItem] = Field(min_length=1, max_length=100)


class ResolveRequest(CurrentApproval):
    item_ids: list[ItemID] = Field(min_length=1, max_length=100)
    reason: Reason


def officer_only(actor):
    if actor.role != "officer":
        raise HTTPException(403, "보완 요청과 처리 확인은 지원 담당자만 실행할 수 있습니다.")


def current_items(session, case, approval_id=None):
    approval = flow.approval_for(session, case, historical=case.status == CaseStatus.COMPLETED.value)
    if approval_id is not None and approval.id != approval_id:
        raise HTTPException(409, "승인 결과가 변경되었습니다. 최신 준비 항목을 다시 불러오세요.")
    return approval, flow.preparation_items(session, case, approval)


def response(case, approval, items, actor):
    unresolved = [i for i in items if not i.supplement_resolved]
    return {"case_id": case.id, "approval_id": approval.id, "status": case.status,
            "can_request": actor.role == "officer" and case.status == CaseStatus.REQUESTED.value,
            "can_restart": actor.role == "user" and case.status == CaseStatus.SUPPLEMENT.value,
            "can_resolve": actor.role == "officer" and case.status == CaseStatus.REQUESTED.value and bool(unresolved),
            "items": [{"id": i.id, "text": i.text, "translated_text": i.translated_text,
                       "prepared": i.prepared, "supplement_reason": i.supplement_reason,
                       "supplement_resolved": i.supplement_resolved} for i in items]}


@router.get("/cases/{case_id}/supplement")
def get_supplement(case_id: CaseID, actor: Actor, session: DB):
    with session.begin():
        case = flow.locked_case(session, case_id)
        if actor.role != "officer":
            flow.owner_only(case, actor)
        if case.status not in {CaseStatus.COLLECTING.value, CaseStatus.REQUESTED.value,
                               CaseStatus.SUPPLEMENT.value, CaseStatus.COMPLETED.value}:
            raise HTTPException(409, "공개된 승인 결과가 있는 준비 건만 보완 내역을 조회할 수 있습니다.")
        approval, items = current_items(session, case)
        return response(case, approval, items, actor)


@router.post("/cases/{case_id}/supplement")
def request_supplement(case_id: CaseID, body: SupplementRequest, actor: Actor, session: DB):
    officer_only(actor)
    with session.begin():
        case = flow.locked_case(session, case_id)
        flow.require_status(case, CaseStatus.REQUESTED)
        approval, items = current_items(session, case, body.approval_id)
        by_id = {i.id: i for i in items}
        ids = [i.id for i in body.items]
        if len(ids) != len(set(ids)) or any(i not in by_id for i in ids):
            raise HTTPException(422, "중복되거나 현재 승인에 속하지 않는 보완 항목입니다.")
        for item in body.items:
            by_id[item.id].supplement_reason = item.reason
            by_id[item.id].supplement_resolved = False
        flow.history(session, case, actor, CaseStatus.SUPPLEMENT,
                     json.dumps({"action": "supplement_requested", "items": [i.model_dump() for i in body.items]},
                                ensure_ascii=False), approval.criterion_versions)
        return response(case, approval, items, actor)


@router.post("/cases/{case_id}/start-revision")
def start_revision(case_id: CaseID, body: CurrentApproval, actor: Actor, session: DB):
    with session.begin():
        case = flow.locked_case(session, case_id)
        flow.owner_only(case, actor)
        flow.require_status(case, CaseStatus.SUPPLEMENT)
        approval, items = current_items(session, case, body.approval_id)
        outstanding = [i for i in items if not i.supplement_resolved]
        if not outstanding:
            raise HTTPException(409, "수정할 미해결 보완 항목이 없습니다.")
        for item in outstanding:
            item.prepared = False
        flow.history(session, case, actor, CaseStatus.COLLECTING,
                     json.dumps({"action": "supplement_revision_started", "item_ids": [i.id for i in outstanding]}),
                     approval.criterion_versions)
        return response(case, approval, items, actor)


@router.post("/cases/{case_id}/resolve-supplements")
def resolve_supplements(case_id: CaseID, body: ResolveRequest, actor: Actor, session: DB):
    officer_only(actor)
    with session.begin():
        case = flow.locked_case(session, case_id)
        flow.require_status(case, CaseStatus.REQUESTED)
        approval, items = current_items(session, case, body.approval_id)
        by_id = {i.id: i for i in items}
        if len(body.item_ids) != len(set(body.item_ids)) or any(i not in by_id for i in body.item_ids):
            raise HTTPException(422, "중복되거나 현재 승인에 속하지 않는 보완 항목입니다.")
        targets = [by_id[i] for i in body.item_ids]
        if any(i.supplement_resolved or i.prepared is not True or i.needs_confirmation for i in targets):
            raise HTTPException(409, "준비함으로 표시된 미해결 보완 항목을 확인한 뒤 처리하세요.")
        for item in targets:
            item.supplement_resolved = True
        flow.history(session, case, actor, CaseStatus.REQUESTED,
                     json.dumps({"action": "supplement_resolved", "item_ids": body.item_ids, "reason": body.reason},
                                ensure_ascii=False), approval.criterion_versions)
        return response(case, approval, items, actor)
