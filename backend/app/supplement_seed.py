"""US-06 전용 모의 승인·준비 항목. 실제 민원·실제 승인 자료가 아니다."""
import os
from datetime import date
from sqlalchemy import select

from .database import build_engine, prepare_workflow_schema, session_factory
from .models import CaseApproval, CaseStatus, CheckResult, Criterion, PreparationCase, PreparationItem


DEMO_CASE_ID = 1106


def seed_supplement_case(session):
    if session.get(PreparationCase, DEMO_CASE_ID) is not None:
        return 0
    criteria = session.scalars(select(Criterion).where(
        Criterion.support_type == "F-6-1", Criterion.office.is_(None), Criterion.is_active.is_(True),
    ).order_by(Criterion.id)).all()
    if any(not c.is_verified for c in criteria):
        raise RuntimeError("미확인 공통 기준이 있습니다. 별도의 빈 모의 DB에서 보완 시드를 실행하세요.")
    if criteria:
        criterion = criteria[0]
    else:
        criterion = Criterion(body="보완 흐름 시연 전용 모의 기준. 실제 민원 기준이 아닙니다.",
                              source="모의 출처 (실제 공식 자료 아님)", checked_on=date(2026, 11, 9),
                              version=1, is_verified=True)
        session.add(criterion)
        criteria.append(criterion)
    case = PreparationCase(id=DEMO_CASE_ID, owner_id="demo-user-1", situation="모의 보완 흐름을 확인하는 가상 사례입니다.",
                           display_language="vi", status=CaseStatus.REQUESTED.value, current_check_task_id="supplement-demo")
    session.add(case)
    session.flush()
    versions = [{"criterion_id": str(c.id), "version": c.version} for c in criteria]
    result = CheckResult(case_id=case.id, situation_version=1, document_version=1, task_id="supplement-demo",
                         analysis_items=[], criterion_versions=versions)
    session.add(result)
    session.flush()
    contents = [("mock-residence", "모의 체류지 준비 자료", "Tài liệu cư trú giả định"),
                ("mock-application", "모의 신청 준비 자료", "Tài liệu đăng ký giả định")]
    approved = [{"id": key, "text": ko, "translated_text": vi, "criterion_id": str(criterion.id),
                 "source": criterion.source, "checked_on": criterion.checked_on.isoformat()} for key, ko, vi in contents]
    approval = CaseApproval(case_id=case.id, result_id=result.id, situation_version=1, document_version=1,
                            criterion_versions=versions, items=approved, display_language="vi", approved_by="demo-officer")
    session.add(approval)
    session.flush()
    for key, ko, vi in contents:
        session.add(PreparationItem(case_id=case.id, approval_id=approval.id, item_key=key, text=ko,
                                    translated_text=vi, criterion_id=criterion.id, prepared=True,
                                    needs_confirmation=False, supplement_resolved=True))
    return 1


def main():
    if os.environ.get("DEMO_MODE") != "1":
        raise SystemExit("모의 DB 전용입니다. DEMO_MODE=1로 실행하세요.")
    engine = build_engine()
    try:
        prepare_workflow_schema(engine)
        with session_factory(engine).begin() as session:
            count = seed_supplement_case(session)
        print(f"보완 시연용 모의 준비 건 {count}개 추가. 기존 건은 덮어쓰지 않았습니다.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
