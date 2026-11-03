"""US-02: 모의 PDF의 페이지별 텍스트 추출. DB·상태·OCR 처리는 하지 않는다."""
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
import logging
import threading

from .identity_patterns import PageText


class ExtractionFailure(StrEnum):
    INVALID_PDF = "invalid_pdf"
    ENCRYPTED = "encrypted_pdf"
    NO_TEXT = "no_text"
    EXTRACTION_ERROR = "extraction_error"


@dataclass(frozen=True)
class ExtractionResult:
    pages: tuple[PageText, ...] = ()
    failure: ExtractionFailure | None = None
    failed_page: int | None = None

    @property
    def ok(self) -> bool:
        return self.failure is None


class _QuietReaderFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.thread_id = threading.get_ident()

    def filter(self, record: logging.LogRecord) -> bool:
        # 파서 경고에 원본 내용이 섞일 수 있어 이 호출의 라이브러리 로그를 억제한다.
        return record.thread != self.thread_id


def extract_pdf(file_name: str, data: bytes) -> ExtractionResult:
    """페이지는 1부터. 일부 페이지라도 텍스트가 없으면 전체 실패로 반환한다.

    실패 시 부분 텍스트·원본·예외 메시지를 반환하거나 기록하지 않는다.
    pypdf 설치 실패는 배포 설정 오류이므로 ImportError를 숨기지 않는다.
    """
    if not data.startswith(b"%PDF-"):
        return ExtractionResult(failure=ExtractionFailure.INVALID_PDF)
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    logger = logging.getLogger("pypdf")
    quiet = _QuietReaderFilter()
    # pypdf는 하위 로거를 쓰므로 각 기존 로거에 필터를 적용한다.
    loggers = [logger] + [
        logging.getLogger(name) for name in logging.Logger.manager.loggerDict
        if name.startswith("pypdf.")
    ]
    for item in loggers:
        item.addFilter(quiet)
    page_number = None
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            return ExtractionResult(failure=ExtractionFailure.ENCRYPTED)
        pages = []
        for page_number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            if not text.strip():
                return ExtractionResult(failure=ExtractionFailure.NO_TEXT, failed_page=page_number)
            pages.append(PageText(file_name, page_number, text))
        if not pages:
            return ExtractionResult(failure=ExtractionFailure.NO_TEXT)
        return ExtractionResult(pages=tuple(pages))
    except PdfReadError:
        return ExtractionResult(failure=ExtractionFailure.INVALID_PDF, failed_page=page_number)
    except Exception:
        return ExtractionResult(failure=ExtractionFailure.EXTRACTION_ERROR, failed_page=page_number)
    finally:
        for item in loggers:
            item.removeFilter(quiet)
