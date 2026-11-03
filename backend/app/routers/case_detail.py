from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..dependencies import DemoActor, get_actor, get_session
from ..models import (
    MAX_FILE_BYTES, MAX_FILES, MAX_SITUATION_LENGTH, PDF_SIGNATURE,
    Attachment, CaseHistory, CaseStatus, CheckResult, PreparationCase,
)
from ..schemas import CaseDetail, CaseSummary, CreateCaseResponse, OfficerCaseDetail


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


def require_user(actor: Annotated[DemoActor, Depends(get_actor)]) -> DemoActor:
    if actor.role != "user":
        raise HTTPException(403, "이용자만 준비 건 생성·본인 목록을 사용할 수 있습니다.")
    return actor


def input_errors(errors: list[dict[str, str]]) -> JSONResponse:
    return JSONResponse(status_code=422, content={"ok": False, "errors": errors})


# 생성과 이후 입력 수정이 같은 규칙을 쓰도록 검사를 함수로 둔다.
def check_situation(form) -> tuple[str | None, list[dict[str, str]]]:
    values = form.getlist("situation")
    situation = values[0] if len(values) == 1 else None
    if not isinstance(situation, str) or not situation.strip():
        return None, [{"field": "situation", "reason": "상황 설명을 입력하세요. 공백·줄바꿈만 입력할 수 없습니다."}]
    if len(situation) > MAX_SITUATION_LENGTH:
        return None, [{"field": "situation", "reason": f"상황 설명은 공백·줄바꿈을 포함해 {MAX_SITUATION_LENGTH:,}자 이하로 입력하세요."}]
    return situation, []


def check_file_count(form) -> tuple[list[UploadFile], list[dict[str, str]]]:
    files = form.getlist("files")
    if not 1 <= len(files) <= MAX_FILES or any(not isinstance(item, UploadFile) for item in files):
        return [], [{"field": "files", "reason": "PDF 파일을 1~5개 선택하세요."}]
    return files, []


async def read_pdfs(files: list[UploadFile]) -> tuple[list[tuple[str, bytes]], list[dict[str, str]]]:
    uploads, errors = [], []
    for file in files:
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf") or len(filename) > 255:
            errors.append({"field": "files", "reason": "파일명은 255자 이하의 .pdf 확장자여야 합니다."})
            continue
        if file.size is not None and file.size > MAX_FILE_BYTES:
            errors.append({"field": "files", "reason": f"{filename}: PDF는 각 10MB 이하여야 합니다."})
            continue
        content = await file.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            errors.append({"field": "files", "reason": f"{filename}: PDF는 각 10MB 이하여야 합니다."})
        elif not content.startswith(PDF_SIGNATURE):
            errors.append({"field": "files", "reason": f"{filename}: PDF 시그니처가 없습니다."})
        else:
            uploads.append((filename, content))
    return uploads, errors


def save_case(session: Session, actor: DemoActor, situation: str, uploads: list[tuple[str, bytes]]) -> CreateCaseResponse:
    with session.begin():
        case = PreparationCase(
            owner_id=actor.id, support_type="F-6-1", situation=situation,
            display_language=None, status=CaseStatus.PREPARING.value,
            situation_version=1, document_version=1,
        )
        session.add(case)
        session.flush()
        for filename, content in uploads:
            session.add(Attachment(
                case_id=case.id, filename=filename, size_bytes=len(content),
                document_version=case.document_version, extracted_text=None, file_data=content,
            ))
        session.flush()
        response = CreateCaseResponse(case=CaseSummary.model_validate(case))
    return response


@router.post(
    "/cases", response_model=CreateCaseResponse, status_code=201,
    openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["support_type", "situation", "files"],
        "properties": {
            "support_type": {"type": "string", "enum": ["F-6-1"]},
            "situation": {"type": "string", "minLength": 1, "maxLength": MAX_SITUATION_LENGTH},
            "files": {"type": "array", "minItems": 1, "maxItems": MAX_FILES,
                      "items": {"type": "string", "format": "binary"}},
        },
    }}}}},
)
async def create_case(
    request: Request,
    actor: Annotated[DemoActor, Depends(require_user)],
    session: Annotated[Session, Depends(get_session)],
):
    media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if media_type != "multipart/form-data":
        return input_errors([{"field": "files", "reason": "PDF를 multipart/form-data로 제출하세요."}])
    try:
        async with request.form(max_files=MAX_FILES + 1, max_fields=8, max_part_size=16384) as form:
            errors = []
            for name in form:
                if name not in {"support_type", "situation", "files"}:
                    errors.append({"field": name, "reason": "지원하지 않는 입력 항목입니다."})
            support_values = form.getlist("support_type")
            if len(support_values) != 1 or support_values[0] != "F-6-1":
                errors.append({"field": "support_type", "reason": "지원 유형은 F-6-1 하나만 제출하세요."})
            situation, situation_errors = check_situation(form)
            files, file_errors = check_file_count(form)
            errors += situation_errors + file_errors
            if errors:
                return input_errors(errors)
            uploads, errors = await read_pdfs(files)
            if errors:
                return input_errors(errors)
            return await run_in_threadpool(save_case, session, actor, situation, uploads)
    except StarletteHTTPException:
        return input_errors([{"field": "files", "reason": "파일 1~5개와 올바른 multipart 입력을 제출하세요."}])


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    actor: Annotated[DemoActor, Depends(require_user)],
    session: Annotated[Session, Depends(get_session)],
):
    cases = session.scalars(
        select(PreparationCase).where(PreparationCase.owner_id == actor.id)
        .order_by(PreparationCase.created_at.desc(), PreparationCase.id.desc())
    )
    return [CaseSummary.model_validate(case) for case in cases]
