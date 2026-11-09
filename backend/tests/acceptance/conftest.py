"""인수 테스트용 입력 fixture.

DB fixture(engine, factory, client)는 상위 tests/conftest.py에서 그대로 받는다.
여기서는 backlog.md US-01 인수 조건의 경계값 입력을 메모리에서 만든다. 파일은 커밋하지 않는다.
아래쪽 LLM fixture는 US-02·03 테스트용이다(app/common/llm_client.py, 이주환 담당. 없으면 해당 테스트만 건너뜀).
"""
import json
from datetime import date

import pytest


MAX_PDF_BYTES = 10_485_760  # US-01 (경계) 10MB
PDF_SIGNATURE = b"%PDF-"


def pdf_bytes(size: int) -> bytes:
    """%PDF- 시그니처로 시작하고 길이가 정확히 size 바이트인 내용."""
    head = PDF_SIGNATURE + b"1.4\n"
    tail = b"\n%%EOF\n"
    return head + b"0" * (size - len(head) - len(tail)) + tail


def pdf_file(name: str = "mock.pdf", size: int = 1024) -> tuple[str, bytes, str]:
    return (name, pdf_bytes(size), "application/pdf")


@pytest.fixture
def pdf_at_limit():
    """US-01 (경계) 정확히 10,485,760바이트 — 받는다."""
    return pdf_file("at-limit.pdf", MAX_PDF_BYTES)


@pytest.fixture
def pdf_over_limit():
    """US-01 (경계) 10,485,761바이트 — 거절한다."""
    return pdf_file("over-limit.pdf", MAX_PDF_BYTES + 1)


@pytest.fixture
def fake_pdf():
    """US-01 (실패·거절) 확장자는 .pdf지만 내용이 PDF 시그니처로 시작하지 않는다."""
    return ("fake.pdf", b"This is plain text, not a PDF.\n", "application/pdf")


@pytest.fixture
def non_pdf_extension():
    """US-01 (실패·거절) 확장자가 .pdf가 아니다."""
    return ("note.txt", b"plain text\n", "text/plain")


@pytest.fixture
def pdf_files():
    """US-01 (경계) 파일 n개 묶음. 0·1·5·6개에 쓴다."""
    return lambda count: [pdf_file(f"mock-{i}.pdf") for i in range(1, count + 1)]


@pytest.fixture
def situations():
    """US-01 (경계) 상황 설명 1자·1,000자(받음), 1,001자(거절).

    공백·줄바꿈이 없는 글자만 써서 1,000자 세는 방법(미정)과 관계없이 길이가 같게 한다.
    """
    return {1: "가", 1000: "가" * 1000, 1001: "가" * 1001}


@pytest.fixture
def counted_situations():
    """US-01 (경계) 1,000자 세는 방법: 공백·줄바꿈을 포함해 센다(API.md 항목 1, 화면은 Array.from().length).

    줄바꿈은 "\\n"만 다룬다("\\r\\n"을 몇 자로 볼지는 질문으로 남김).
    """
    return {
        "1000_with_spaces": "가 " * 500,  # 공백 포함 1,000자 → 받음
        "1001_with_spaces": "가 " * 500 + "가",  # 공백 포함 1,001자 → 거절
        "1000_with_newlines": "가" * 499 + "\n\n" + "가" * 499,  # 줄바꿈 포함 1,000자 → 받음
        "1001_with_newlines": "가" * 500 + "\n" + "가" * 500,  # 줄바꿈 포함 1,001자 → 거절
    }


@pytest.fixture
def blank_situations():
    """US-01 (실패·거절) 빈 상황 설명(공백·줄바꿈만 있는 경우 포함)."""
    return ["", "   ", "\n\n", " \n\t "]


# --- US-02 LLM 모의 응답 fixture ---------------------------------------------
# llm_client가 main에 없으면 이 fixture를 쓰는 테스트만 건너뛴다(US-01·04 테스트는 영향 없음).

MOCK_CRITERION_ID = "mock-criterion-1"


@pytest.fixture
def llm():
    return pytest.importorskip("app.common.llm_client")


@pytest.fixture
def check_input(llm):
    """식별정보 없는 모의 상황·PDF 추출 텍스트·등록 기준 1개. 실제 공식 출처가 아니다."""
    return llm.CheckInput(
        situation="결혼이민자 체류기간 연장을 준비하고 있습니다. 어떤 서류가 더 필요한지 알고 싶습니다.",
        document_texts=("모의 서류 1쪽: 가족관계 확인용 모의 문서입니다.",),
        criteria=(llm.CriterionInput(
            criterion_id=MOCK_CRITERION_ID, body="모의 기준 본문입니다.",
            source="모의 출처(실제 공식 출처 아님)", checked_on=date(2026, 11, 3),
        ),),
    )


class RecordingTransport:
    """LLM에 보낸 요청 본문을 모두 기록한다. 응답은 감싼 transport 또는 고정 문자열."""

    def __init__(self, inner=None, raw=None):
        self.inner, self.raw, self.payloads = inner, raw, []

    async def generate(self, payload: dict) -> str:
        self.payloads.append(payload)
        if self.raw is not None:
            return self.raw
        return await self.inner.generate(payload)

    @property
    def sent_text(self) -> str:
        return json.dumps(self.payloads, ensure_ascii=False)


@pytest.fixture
def llm_transport(llm):
    """US-02 모의 응답: mode는 success·error·delay·invalid. 보낸 요청은 .payloads에 남는다."""
    return lambda mode="success", **kw: RecordingTransport(llm.MockTransport(mode, **kw))


@pytest.fixture
def llm_fixed_response():
    """US-02 근거 기준 ID 시험용: 정해진 응답(dict)을 그대로 돌려주는 transport."""
    return lambda body: RecordingTransport(raw=json.dumps(body, ensure_ascii=False))
