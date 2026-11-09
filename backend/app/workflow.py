"""US-02·03·05·07. DB 트랜잭션과 외부 LLM 호출을 분리한다."""
from dataclasses import asdict
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update
from starlette.concurrency import run_in_threadpool

from .common.identity_patterns import find_identity_patterns, kinds_in
from .common.llm_client import CheckClientError, CheckInput, CriterionInput, build_payload, check_documents
from .common.pdf_extraction import extract_pdf
from .models import (
    Attachment, CaseApproval, CaseHistory, CaseStatus, CheckResult, Criterion,
    MAX_FILES, MAX_FILE_BYTES, MAX_SITUATION_LENGTH, PreparationCase, PreparationItem, utc_now,
)


def locked_case(session, case_id):
    case = session.scalar(select(PreparationCase).where(PreparationCase.id == case_id).with_for_update())
    if case is None:
        raise HTTPException(404, "준비 건을 찾을 수 없습니다.")
    return case


def owner_only(case, actor):
    if actor.role != "user" or actor.id != case.owner_id:
        raise HTTPException(403, "해당 준비 건의 이용자만 실행할 수 있습니다.")


def require_status(case, expected):
    if case.status != expected.value:
        raise HTTPException(409, f"{expected.value} 상태에서만 실행할 수 있습니다.")


def criteria_for(session, case, *, lock=True):
    # 비활성·미검증 기준도 읽어 버전 변경/추가를 감지한다. 관서 미선택 시 공통만 적용.
    query = select(Criterion).where(Criterion.support_type == case.support_type).order_by(Criterion.id)
    if lock:
        query = query.with_for_update()
    rows = session.scalars(query).all()
    return [c for c in rows if c.is_active and (c.office is None or c.office == case.office)]


def versions(criteria):
    return [{"criterion_id": str(c.id), "version": c.version} for c in criteria]


def versions_match(session, case, recorded):
    current = criteria_for(session, case)
    return bool(recorded) and recorded == versions(current) and all(c.is_verified for c in current)


def history(session, case, actor, to_status, reason="", criterion_versions=None):
    now = utc_now()
    session.add(CaseHistory(
        case_id=case.id, from_status=case.status, to_status=to_status.value,
        actor_id=actor.id, actor_role=actor.role, reason=reason,
        criterion_versions=criterion_versions or [], occurred_at=now,
    ))
    case.status = to_status.value
    return now


def active_result(session, case, result_id=None):
    query = select(CheckResult).where(CheckResult.case_id == case.id, CheckResult.invalidated_at.is_(None))
    if result_id is not None:
        query = query.where(CheckResult.id == result_id)
    result = session.scalar(query.order_by(CheckResult.id.desc()).limit(1).with_for_update())
    if (result is None or not result.task_id or result.task_id != case.current_check_task_id
            or result.situation_version != case.situation_version
            or result.document_version != case.document_version
            or not versions_match(session, case, result.criterion_versions)):
        raise HTTPException(409, "현재 입력·기준과 일치하는 점검 결과가 없습니다. 재점검하세요.")
    return result


def approval_for(session, case, *, historical=False):
    approval = session.scalar(select(CaseApproval).where(
        CaseApproval.case_id == case.id, CaseApproval.invalidated_at.is_(None),
    ).order_by(CaseApproval.id.desc()).limit(1).with_for_update())
    if (approval is None or (not historical and (approval.situation_version != case.situation_version
            or approval.document_version != case.document_version
            or approval.display_language != case.display_language
            or not versions_match(session, case, approval.criterion_versions)))):
        raise HTTPException(409, "승인 결과가 현재 입력·기준과 다릅니다. 재점검·재승인하세요.")
    result = session.get(CheckResult, approval.result_id)
    if result is None or result.invalidated_at is not None:
        raise HTTPException(409, "승인된 점검 결과가 무효화되었습니다.")
    return approval


def preparation_items(session, case, approval):
    return session.scalars(select(PreparationItem).where(
        PreparationItem.case_id == case.id, PreparationItem.approval_id == approval.id,
    ).order_by(PreparationItem.id).with_for_update()).all()


def read_inputs(factory, case_id, actor):
    with factory() as session:
        case = session.get(PreparationCase, case_id)
        if case is None:
            raise HTTPException(404, "준비 건을 찾을 수 없습니다.")
        owner_only(case, actor)
        require_status(case, CaseStatus.PREPARING)
        attachments = session.scalars(select(Attachment).where(
            Attachment.case_id == case.id, Attachment.document_version == case.document_version,
        ).order_by(Attachment.id)).all()
        if (not case.situation.strip() or len(case.situation) > MAX_SITUATION_LENGTH
                or not 1 <= len(attachments) <= MAX_FILES):
            raise HTTPException(422, "상황 설명과 PDF 1~5개를 확인하세요.")
        return {
            "situation": case.situation, "situation_version": case.situation_version,
            "document_version": case.document_version,
            "attachments": [(a.id, a.filename, a.file_data) for a in attachments],
        }


def extract_inputs(snapshot):
    pages = []
    for _, name, data in snapshot["attachments"]:
        if data is None or len(data) > MAX_FILE_BYTES:
            raise HTTPException(422, {"code": "pdf_missing", "file_name": name,
                                      "message": "모의 PDF를 다시 등록하세요."})
        result = extract_pdf(name, data)
        if not result.ok:
            raise HTTPException(422, {"code": "pdf_extraction_failed", "file_name": name,
                                      "page": result.failed_page,
                                      "message": "텍스트를 읽을 수 있는 모의 PDF로 바꿔 주세요. OCR은 지원하지 않습니다."})
        pages.extend(result.pages)
    findings = find_identity_patterns(snapshot["situation"], pages)
    if findings:
        raise HTTPException(422, {"code": "identifying_input", "locations": [asdict(f) for f in findings],
                                  "message": "식별정보 패턴을 제거한 모의 자료로 수정하세요."})
    return pages


def start_check(factory, case_id, actor, snapshot, pages):
    with factory.begin() as session:
        case = locked_case(session, case_id)
        owner_only(case, actor)
        require_status(case, CaseStatus.PREPARING)
        if (case.situation_version != snapshot["situation_version"]
                or case.document_version != snapshot["document_version"]
                or case.situation != snapshot["situation"]):
            raise HTTPException(409, "입력이 변경되었습니다. 다시 점검하세요.")
        criteria = criteria_for(session, case)
        if not criteria or not any(c.office is None for c in criteria):
            raise HTTPException(409, "등록된 공통 기준이 없습니다. 담당자에게 문의하세요.")
        if any(not c.is_verified for c in criteria):
            raise HTTPException(409, "관서 확인 필요: 적용 기준의 출처·최신 여부를 담당자가 확인해야 합니다.")
        if any(not c.body.strip() or not c.source.strip() for c in criteria):
            raise HTTPException(409, "등록 기준의 본문·출처를 담당자가 확인해야 합니다.")
        request = CheckInput(
            situation=case.situation, document_texts=tuple(p.text for p in pages),
            support_type=case.support_type,
            criteria=tuple(CriterionInput(criterion_id=str(c.id), body=c.body, source=c.source,
                                          checked_on=c.checked_on) for c in criteria),
        )
        try:
            build_payload(request)
        except CheckClientError:
            raise HTTPException(422, "등록 기준 또는 입력에 전송할 수 없는 내용이 있습니다. 담당자에게 문의하세요.") from None
        task_id = uuid4().hex
        case.current_check_task_id = task_id
        session.execute(update(CheckResult).where(
            CheckResult.case_id == case.id, CheckResult.invalidated_at.is_(None),
        ).values(invalidated_at=utc_now()))
        session.execute(update(CaseApproval).where(
            CaseApproval.case_id == case.id, CaseApproval.invalidated_at.is_(None),
        ).values(invalidated_at=utc_now()))
        recorded = versions(criteria)
        history(session, case, actor, CaseStatus.CHECKING, criterion_versions=recorded)
        return task_id, request, recorded


def finish_check(factory, case_id, actor, snapshot, task_id, recorded, analysis, failure):
    with factory.begin() as session:
        case = locked_case(session, case_id)
        if (case.status != CaseStatus.CHECKING.value or case.current_check_task_id != task_id
                or case.situation_version != snapshot["situation_version"]
                or case.document_version != snapshot["document_version"]
                or not versions_match(session, case, recorded)):
            return {"case_id": case.id, "status": case.status, "discarded": True}
        criteria = {str(c.id): c for c in criteria_for(session, case)}
        items = []
        if analysis:
            for group in ("cautions", "possible_omissions", "additional_documents"):
                for item in getattr(analysis, group):
                    criterion = criteria.get(item.criterion_id)
                    # 모형이 식별정보를 만들어도 저장·공개 가능한 항목으로 취급하지 않는다.
                    unsafe = bool(kinds_in(item.text))
                    items.append({
                        "id": uuid4().hex, "kind": group,
                        "text": "응답에 식별정보 패턴이 있어 내용을 저장하지 않았습니다." if unsafe else item.text,
                        "criterion_id": item.criterion_id if criterion else None,
                        "source": criterion.source if criterion else None,
                        "checked_on": criterion.checked_on.isoformat() if criterion else None,
                        "needs_confirmation": criterion is None or unsafe,
                    })
        result = CheckResult(
            case_id=case.id, task_id=task_id, situation_version=case.situation_version,
            document_version=case.document_version, criterion_versions=recorded,
            analysis_items=items, failure_reason=failure,
        )
        session.add(result)
        history(session, case, actor, CaseStatus.REVIEWING,
                reason="자동 점검 실패" if failure else "", criterion_versions=recorded)
        session.flush()
        # 이용자에게는 결과 ID·내용·실패 원문을 노출하지 않는다.
        return {"case_id": case.id, "status": case.status, "discarded": False,
                "message": "담당자 검토 중"}


async def perform_check(factory, case_id, actor, transport, *, timeout=60):
    snapshot = await run_in_threadpool(read_inputs, factory, case_id, actor)
    pages = await run_in_threadpool(extract_inputs, snapshot)
    task_id, request, recorded = await run_in_threadpool(start_check, factory, case_id, actor, snapshot, pages)
    analysis, failure = None, None
    try:
        analysis = await check_documents(request, transport, timeout=timeout)
    except CheckClientError as error:
        failure = error.code.value
    return await run_in_threadpool(finish_check, factory, case_id, actor, snapshot,
                                  task_id, recorded, analysis, failure)
