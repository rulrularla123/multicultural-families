import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .database import build_engine, session_factory
from .models import CaseHistory, CaseStatus, CheckResult, PreparationCase, utc_now
from .schemas import CaseDetail, OfficerCaseDetail, RejectRequest, RejectResponse


@dataclass(frozen=True)
class DemoActor:
    id: str
    role: str


DEMO_ACTORS = {
    "demo-officer": DemoActor("demo-officer", "officer"),
    "demo-user-1": DemoActor("demo-user-1", "user"),
    "demo-user-2": DemoActor("demo-user-2", "user"),
}


def get_actor(
    request: Request,
    account: Annotated[str | None, Header(alias="X-Demo-Account")] = None,
) -> DemoActor:
    if not request.app.state.demo_mode:
        raise HTTPException(503, "모의 계정 모드가 활성화되지 않았습니다.")
    actor = DEMO_ACTORS.get(account or "")
    if actor is None:
        raise HTTPException(401, "유효한 모의 계정을 선택하세요.")
    return actor


def require_officer(actor: Annotated[DemoActor, Depends(get_actor)]) -> DemoActor:
    if actor.role != "officer":
        raise HTTPException(403, "지원 담당자만 반려할 수 있습니다.")
    return actor


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def create_app(engine: Engine | None = None, demo_mode: bool | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        enabled = demo_mode if demo_mode is not None else os.environ.get("DEMO_MODE") == "1"
        if not enabled:
            raise RuntimeError("로컬 모의 계정 시연 전용입니다. DEMO_MODE=1로 실행하세요.")
        db_engine = engine if engine is not None else build_engine()
        app.state.demo_mode = enabled
        app.state.session_factory = session_factory(db_engine)
        try:
            yield
        finally:
            if engine is None:
                db_engine.dispose()

    app = FastAPI(title="준비 건 담당자 반려 API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Demo-Account"],
    )

    @app.get("/cases/{case_id}")
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

    @app.post("/cases/{case_id}/reject", response_model=RejectResponse)
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
                actor_id=actor.id, actor_role=actor.role, reason=body.reason,
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

    return app


app = create_app()
