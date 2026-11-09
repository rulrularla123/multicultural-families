"""민건 담당 US-02·03·05·07. 기존 case_detail router에서 조립한다."""
import json
from datetime import timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common.llm_client import MockTransport
from ..dependencies import DemoActor, get_actor, get_session
from ..models import CaseApproval, CaseHistory, CaseStatus, PreparationItem
from .. import workflow as flow


router = APIRouter()
CaseID = Annotated[int, Path(gt=0, le=18446744073709551615)]
Actor = Annotated[DemoActor, Depends(get_actor)]
DB = Annotated[Session, Depends(get_session)]
Nonblank = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=10000)]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ResultRequest(StrictBody):
    result_id: int = Field(gt=0)


class ReviewedItem(StrictBody):
    id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
    kind: Annotated[str, StringConstraints(pattern=r"^(cautions|possible_omissions|additional_documents)$")]
    text: Nonblank
    criterion_id: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$")]
    translated_text: Nonblank | None = None


class ReviewRequest(ResultRequest):
    items: list[ReviewedItem] = Field(min_length=1, max_length=100)
    reason: Nonblank
    translation_confirmed: bool = False


class ItemChoice(StrictBody):
    id: int = Field(gt=0)
    prepared: bool


class ChoicesRequest(StrictBody):
    items: list[ItemChoice] = Field(min_length=1, max_length=100)


class CompleteRequest(StrictBody):
    notice_translation: Nonblank
    translation_confirmed: bool


def officer_only(actor):
    if actor.role != "officer":
        raise HTTPException(403, "지원 담당자만 실행할 수 있습니다.")


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat()


def item_response(item):
    return {"id": item.id, "item_key": item.item_key, "text": item.text,
            "translated_text": item.translated_text, "criterion_id": str(item.criterion_id),
            "prepared": item.prepared, "needs_confirmation": item.needs_confirmation,
            "supplement_reason": item.supplement_reason,
            "supplement_resolved": item.supplement_resolved}


@router.post("/cases/{case_id}/check")
async def check_case(case_id: CaseID, request: Request, actor: Actor):
    # 키·모델 선택은 공유 설정 담당이 명시 주입한다. 기본은 외부 호출 없는 모의 클라이언트.
    transport = getattr(request.app.state, "check_transport", None)
    if transport is None:
        transport = MockTransport()
    return await flow.perform_check(request.app.state.session_factory, case_id, actor, transport)


@router.get("/cases/{case_id}/check-result")
def check_result(case_id: CaseID, actor: Actor, session: DB):
    officer_only(actor)
    with session.begin():
        case = flow.locked_case(session, case_id)
        flow.require_status(case, CaseStatus.REVIEWING)
        result = flow.active_result(session, case)
        reviewed = result.reviewed_items
        can_approve = (bool(reviewed) and bool(result.review_reason) and case.display_language == "vi"
                       and all(not i.get("needs_confirmation", True) and i.get("criterion_id")
                               and i.get("translated_text") and i.get("translation_confirmed") for i in reviewed))
        return {"case_id": case.id, "result_id": result.id, "status": case.status,
                "can_approve": can_approve,
                "analysis_items": result.analysis_items, "reviewed_items": result.reviewed_items,
                "failure_reason": result.failure_reason, "review_reason": result.review_reason,
                "criterion_versions": result.criterion_versions,
                "situation_version": result.situation_version, "document_version": result.document_version}


@router.post("/cases/{case_id}/review")
def review_case(case_id: CaseID, body: ReviewRequest, actor: Actor, session: DB):
    officer_only(actor)
    with session.begin():
        case = flow.locked_case(session, case_id)
        flow.require_status(case, CaseStatus.REVIEWING)
        result = flow.active_result(session, case, body.result_id)
        if not body.translation_confirmed or any(not i.translated_text for i in body.items):
            raise HTTPException(422, "담당자가 베트남어 번역문을 확인하고 확인 여부를 표시해야 합니다.")
        ids = [i.id for i in body.items]
        if len(ids) != len(set(ids)):
            raise HTTPException(422, "검토 항목 ID가 중복됩니다.")
        criteria = {str(c.id): c for c in flow.criteria_for(session, case)}
        reviewed = []
        for item in body.items:
            criterion = criteria.get(item.criterion_id)
            if criterion is None or not criterion.is_verified:
                raise HTTPException(422, "점검에 적용된 확인된 기준을 근거로 지정하세요.")
            if flow.kinds_in(item.text) or flow.kinds_in(item.translated_text or ""):
                raise HTTPException(422, "공개 항목에 식별정보 패턴을 포함할 수 없습니다.")
            reviewed.append({**item.model_dump(), "source": criterion.source,
                             "checked_on": criterion.checked_on.isoformat(), "needs_confirmation": False,
                             "translation_confirmed": True})
        case.display_language = "vi"
        result.reviewed_items = reviewed
        result.review_reason = body.reason
        # 삭제한 초안도 남겨 단순 삭제로 미해결 문제를 숨기는 경로를 없앤다.
        audit = json.dumps({"reason": body.reason, "result_id": result.id,
                            "reviewed_items": reviewed,
                            "removed_ids": [i.get("id") for i in result.analysis_items if i.get("id") not in ids],
                            "resolved_failure": result.failure_reason}, ensure_ascii=False)
        flow.history(session, case, actor, CaseStatus.REVIEWING, audit, result.criterion_versions)
        return {"case_id": case.id, "result_id": result.id, "status": case.status,
                "items": reviewed}


@router.post("/cases/{case_id}/approve")
def approve_case(case_id: CaseID, body: ResultRequest, actor: Actor, session: DB):
    officer_only(actor)
    with session.begin():
        case = flow.locked_case(session, case_id)
        flow.require_status(case, CaseStatus.REVIEWING)
        result = flow.active_result(session, case, body.result_id)
        items = result.reviewed_items if result.reviewed_items is not None else result.analysis_items
        if ((result.failure_reason and not result.review_reason) or not items
                or any(i.get("needs_confirmation", True) or not i.get("criterion_id") for i in items)):
            raise HTTPException(409, "자동 점검 실패·확인 필요 항목을 근거와 처리 사유를 남겨 해결하세요.")
        if (case.display_language != "vi" or any(
                not i.get("translated_text") or not i.get("translation_confirmed") for i in items)):
            raise HTTPException(409, "담당자가 확인한 베트남어 번역문이 필요합니다.")
        now = flow.history(session, case, actor, CaseStatus.COLLECTING,
                           criterion_versions=result.criterion_versions)
        approval = CaseApproval(
            case_id=case.id, result_id=result.id, situation_version=case.situation_version,
            document_version=case.document_version, criterion_versions=result.criterion_versions,
            items=items, display_language=case.display_language, approved_by=actor.id, approved_at=now,
        )
        session.add(approval)
        session.flush()
        for item in items:
            session.add(PreparationItem(
                case_id=case.id, approval_id=approval.id, item_key=item["id"], text=item["text"],
                translated_text=item.get("translated_text"), criterion_id=int(item["criterion_id"]),
                prepared=None, needs_confirmation=False, supplement_resolved=True,
            ))
        return {"case_id": case.id, "approval_id": approval.id, "status": case.status,
                "approved_at": iso(now), "bilingual_ready": bool(case.display_language)}


@router.get("/cases/{case_id}/approved-result")
def approved_result(case_id: CaseID, actor: Actor, session: DB):
    with session.begin():
        case = flow.locked_case(session, case_id)
        if actor.role != "officer":
            flow.owner_only(case, actor)
        if case.status not in {CaseStatus.COLLECTING.value, CaseStatus.REQUESTED.value,
                               CaseStatus.SUPPLEMENT.value, CaseStatus.COMPLETED.value}:
            raise HTTPException(409, "담당자 검토 중이거나 공개할 승인 결과가 없습니다.")
        approval = flow.approval_for(session, case, historical=case.status == CaseStatus.COMPLETED.value)
        items = flow.preparation_items(session, case, approval)
        completion = session.scalar(select(CaseHistory).where(
            CaseHistory.case_id == case.id, CaseHistory.to_status == CaseStatus.COMPLETED.value,
        ).order_by(CaseHistory.id.desc()).limit(1)) if case.status == CaseStatus.COMPLETED.value else None
        notice = json.loads(completion.reason) if completion else None
        return {"case_id": case.id, "approval_id": approval.id, "status": case.status,
                "display_language": approval.display_language, "bilingual_ready": bool(approval.display_language),
                "items": approval.items, "preparation_items": [item_response(i) for i in items],
                "not_prepared_count": sum(i.prepared is False for i in items),
                "approved_at": iso(approval.approved_at), "completion_notice": notice}


@router.post("/cases/{case_id}/preparation-items")
def save_choices(case_id: CaseID, body: ChoicesRequest, actor: Actor, session: DB):
    with session.begin():
        case = flow.locked_case(session, case_id)
        flow.owner_only(case, actor)
        flow.require_status(case, CaseStatus.COLLECTING)
        approval = flow.approval_for(session, case)
        items = flow.preparation_items(session, case, approval)
        by_id = {i.id: i for i in items}
        ids = [i.id for i in body.items]
        if len(ids) != len(set(ids)) or any(i not in by_id for i in ids):
            raise HTTPException(422, "중복되거나 현재 승인에 속하지 않는 준비 항목입니다.")
        for choice in body.items:
            by_id[choice.id].prepared = choice.prepared
        return {"case_id": case.id, "status": case.status, "items": [item_response(i) for i in items]}


@router.post("/cases/{case_id}/request-confirmation")
def request_confirmation(case_id: CaseID, actor: Actor, session: DB):
    with session.begin():
        case = flow.locked_case(session, case_id)
        flow.owner_only(case, actor)
        flow.require_status(case, CaseStatus.COLLECTING)
        approval = flow.approval_for(session, case)
        items = flow.preparation_items(session, case, approval)
        missing = [i.id for i in items if i.prepared is None]
        if not items or missing:
            raise HTTPException(409, {"message": "모든 항목에서 준비함/아직을 선택하세요.", "unselected_item_ids": missing})
        now = flow.history(session, case, actor, CaseStatus.REQUESTED,
                           criterion_versions=approval.criterion_versions)
        return {"case_id": case.id, "status": case.status, "requested_at": iso(now),
                "not_prepared_count": sum(i.prepared is False for i in items)}


@router.post("/cases/{case_id}/complete")
def complete_case(case_id: CaseID, body: CompleteRequest, actor: Actor, session: DB):
    officer_only(actor)
    with session.begin():
        case = flow.locked_case(session, case_id)
        flow.require_status(case, CaseStatus.REQUESTED)
        approval = flow.approval_for(session, case)
        items = flow.preparation_items(session, case, approval)
        reasons = []
        if not items or any(i.prepared is not True for i in items):
            reasons.append("모든 항목을 준비함으로 표시해야 합니다.")
        if any(i.needs_confirmation or not i.supplement_resolved for i in items):
            reasons.append("미해결 보완·확인 필요 항목이 있습니다.")
        if case.display_language != "vi" or not body.translation_confirmed:
            reasons.append("담당자가 확인한 베트남어 완료 안내 문구가 필요합니다.")
        if reasons:
            raise HTTPException(409, {"reasons": reasons})
        reason = json.dumps({"notice_ko": "민원 접수나 체류기간 연장 허가가 아닙니다",
                             "display_language": case.display_language,
                             "notice_translation": body.notice_translation}, ensure_ascii=False)
        now = flow.history(session, case, actor, CaseStatus.COMPLETED, reason, approval.criterion_versions)
        return {"case_id": case.id, "status": case.status, "completed_at": iso(now),
                "notice_ko": "민원 접수나 체류기간 연장 허가가 아닙니다",
                "notice_translation": body.notice_translation, "bilingual_ready": bool(case.display_language)}
