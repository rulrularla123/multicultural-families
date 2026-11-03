"""인수 테스트용 입력 fixture.

DB fixture(engine, factory, client)는 상위 tests/conftest.py에서 그대로 받는다.
여기서는 backlog.md US-01 인수 조건의 경계값 입력만 메모리에서 만든다. 파일은 커밋하지 않는다.
요청 필드 이름·경로는 API.md 항목 1이 합의되면 테스트 쪽에서 붙인다.
"""
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
    """US-01 (경계) 1,000자 세는 방법: 공백은 세고 줄바꿈은 세지 않는다.

    2026-11-03 김태후 제안. 김민건 확인·API.md 기록 전이라 생성 API 테스트에는 기록 뒤에 쓴다.
    줄바꿈은 "\\n"만 다룬다("\\r\\n"은 질문으로 남김).
    """
    return {
        "1000_with_spaces": "가 " * 500,  # 공백 포함 1,000자 → 받음
        "1001_with_spaces": "가 " * 500 + "가",  # 공백 포함 1,001자 → 거절
        "1000_plus_newlines": "가" * 500 + "\n\n" + "가" * 500,  # 줄바꿈 빼면 1,000자 → 받음
    }


@pytest.fixture
def blank_situations():
    """US-01 (실패·거절) 빈 상황 설명(공백·줄바꿈만 있는 경우 포함)."""
    return ["", "   ", "\n\n", " \n\t "]
