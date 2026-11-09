import os
from datetime import date

from .database import build_engine, session_factory
from .models import Base, CaseStatus, CheckResult, Criterion, PreparationCase


DEMO_CASES = [
    (1001, "demo-user-1", "체류기간 연장을 위해 준비한 서류를 확인하고 싶습니다.", CaseStatus.REVIEWING),
    (1002, "demo-user-2", "추가로 준비할 서류가 있는지 알고 싶습니다.", CaseStatus.REVIEWING),
    (1003, "demo-user-1", "준비 목록을 다시 확인하고 싶습니다.", CaseStatus.PREPARING),
    (1004, "demo-user-1", "모의 항목 준비가 끝난 사례입니다.", CaseStatus.COMPLETED),
    (1005, "demo-user-1", "준비를 중단한 모의 사례입니다.", CaseStatus.CANCELED),
]


def seed_demo(session, display_language: str):
    created = 0
    for case_id, owner, situation, status in DEMO_CASES:
        if session.get(PreparationCase, case_id) is not None:
            continue
        case = PreparationCase(
            id=case_id, owner_id=owner, situation=situation, display_language=display_language,
            status=status.value, situation_version=1, document_version=1,
        )
        session.add(case)
        session.flush()
        if status == CaseStatus.REVIEWING:
            session.add(CheckResult(
                case_id=case_id, situation_version=1, document_version=1,
                analysis_items=[{"kind": "주의점", "text": "공개하면 안 되는 모의 분석 초안"}],
                criterion_versions=[],
            ))
        created += 1
    return created


# 첫 데모용 공통 기준 1개 버전 (PRD 10절). 실제 공식 기준·출처가 아니다.
# seed_demo와 분리해 둔다. 테스트는 기준이 없는 상태에서 시작해 필요한 기준을 직접 넣는다.
DEMO_CRITERION = dict(
    support_type="F-6-1", office=None,
    body="개발용 모의 공통 기준입니다. 실제 체류기간 연장 기준이 아닙니다. "
         "모의 상황 설명과 모의 PDF를 대조해 주의점과 추가 준비 서류 후보를 정리하는 데모에만 씁니다.",
    source="모의 출처 (실제 공식 문서 아님)", checked_on=date(2026, 11, 9),
    version=1, is_verified=True, is_active=True,
)


def seed_criteria(session):
    """공통 기준이 하나도 없을 때만 넣는다. 기존 기준은 덮어쓰지 않는다."""
    exists = session.query(Criterion).filter(Criterion.office.is_(None)).first()
    if exists is not None:
        return 0
    session.add(Criterion(**DEMO_CRITERION))
    return 1


def main():
    if os.environ.get("DEMO_MODE") != "1":
        raise SystemExit("모의 데이터 전용입니다. DEMO_MODE=1로 실행하세요.")
    language = os.environ.get("DEMO_LANGUAGE")
    if not language or not language.strip():
        raise SystemExit("DEMO_LANGUAGE에 팀이 선택한 표시 언어를 지정하세요.")
    engine = build_engine()
    try:
        Base.metadata.create_all(engine)
        with session_factory(engine).begin() as session:
            count = seed_demo(session, language)
            criteria = seed_criteria(session)
        print(f"모의 준비 건 {count}개, 공통 기준 {criteria}개 추가. 기존 데이터는 덮어쓰지 않았습니다.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
