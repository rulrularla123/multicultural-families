"""개발용 가짜 응답(LLM_FAKE)의 질의 재작성: 화면 추천 질문이 시연에서 근거 조문을 찾는지.

실제 OpenAI 재작성의 품질을 확인하는 테스트가 아니다. 키 없이 시연할 때 추천 질문이
"근거 조문을 찾지 못했다"로 끝나지 않는지만 확인한다.
"""
import re
from pathlib import Path

import pytest

from app.llm_fake import _glossary_terms

SUGGESTED = re.findall(
    r"'chat\.suggested\.\d':\s*'([^']+)'",
    (Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n.ts").read_text(encoding="utf-8"),
)
VI_SUGGESTED = [q for q in SUGGESTED if not re.search(r"[가-힣]", q)]


@pytest.mark.parametrize("question, expected", [
    ("Khi nào phải nộp đơn gia hạn lưu trú?", "체류기간 연장허가"),
    ("Đổi địa chỉ thì phải khai báo thế nào?", "체류지 변경신고"),
    ("Nếu ly hôn thì tư cách lưu trú sẽ ra sao?", "이혼"),
    ("Điều kiện xin nhập quốc tịch là gì?", "귀화허가"),
    ("Tôi muốn hỏi về visa F-6", "결혼이민(F-6) 체류자격"),
])
def test_vietnamese_question_maps_to_korean_legal_term(question, expected):
    """베트남어 용어는 음절이 짧아 두 음절 묶음으로 대조한다 ('gia hạn' → 체류기간 연장허가)."""
    assert expected in _glossary_terms(question)[:3]


def test_unrelated_question_has_no_terms():
    assert _glossary_terms("Hôm nay trời đẹp quá") == []


def test_suggested_questions_are_read_from_screen():
    assert len(VI_SUGGESTED) == 4


@pytest.mark.db
@pytest.mark.parametrize("question", VI_SUGGESTED)
def test_vietnamese_suggested_question_gets_citations_in_fake_mode(question):
    """화면의 베트남어 추천 질문은 LLM_FAKE에서도 근거 조문이 붙는다 (시연 대비)."""
    from fastapi.testclient import TestClient

    from app.core.db import engine
    from app.main import app

    with TestClient(app) as c:
        r = c.post("/api/v1/chat", json={"message": question, "lang": "vi"})
        c.portal.call(engine.dispose)
    assert r.status_code == 200
    assert r.json()["citations"], f"근거 조문 없음: {question}"
