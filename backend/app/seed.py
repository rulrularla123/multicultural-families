import os

from .database import build_engine, session_factory
from .models import Base, CaseStatus, CheckResult, PreparationCase


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
        print(f"모의 준비 건 {count}개 추가. 기존 건은 덮어쓰지 않았습니다.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
