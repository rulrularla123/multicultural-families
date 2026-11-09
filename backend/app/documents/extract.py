"""업로드 문서에서 텍스트를 뽑는다. 글자가 있는 PDF·DOCX만 받는다 (스캔·사진 서류의 OCR은 MVP 범위 밖).

쪽 경계는 폼피드(\\f)로 남긴다. 조항 분할(segment.py)이 이를 읽어 조항마다 쪽 번호를 붙인다.
"""

import io
from dataclasses import dataclass

MAX_BYTES = 10 * 1024 * 1024  # 10,485,760바이트까지 받는다
MAX_CHARS = 80_000
MIN_TEXT_CHARS = 30
PAGE_BREAK = "\f"

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

MESSAGES = {
    "too_large": {"vi": "Tệp quá lớn (tối đa 10MB).", "ko": "파일이 너무 큽니다 (최대 10MB)."},
    "unsupported": {"vi": "Chỉ nhận tệp PDF hoặc DOCX.", "ko": "PDF 또는 DOCX 파일만 올릴 수 있습니다."},
    "no_text": {
        "vi": "Không đọc được chữ trong tệp này. Tệp quét hoặc ảnh chụp chưa được hỗ trợ — hãy dùng PDF có chữ hoặc DOCX.",
        "ko": "이 파일에서 글자를 읽지 못했습니다. 스캔·사진 서류는 아직 지원하지 않습니다. 글자가 있는 PDF나 DOCX를 올려 주세요.",
    },
}


class UnsupportedDocument(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


@dataclass
class Extracted:
    text: str  # 쪽 사이는 \f
    page_count: int | None
    method: str  # pdf-text | docx


def count_pages(text: str) -> int:
    return text.count(PAGE_BREAK) + 1


def _kind(filename: str, mime: str | None) -> str | None:
    name = filename.lower()
    if name.endswith(".pdf") or mime == PDF:
        return PDF
    if name.endswith(".docx") or mime == DOCX:
        return DOCX
    return None


def _docx_text(data: bytes) -> str:
    """본문을 문서 순서대로 읽는다. 명시적 쪽 나누기(w:br type=page)는 \\f로 바꾼다."""
    from docx import Document

    doc = Document(io.BytesIO(data))
    out: list[str] = []
    for el in doc.element.body.iterchildren():
        if el.tag == _W + "p":
            line = []
            for node in el.iter(_W + "t", _W + "br", _W + "tab"):
                if node.tag == _W + "t":
                    line.append(node.text or "")
                elif node.tag == _W + "tab":
                    line.append("\t")
                elif node.get(_W + "type") == "page":
                    out.append("".join(line))
                    out.append(PAGE_BREAK)
                    line = []
                else:
                    line.append("\n")
            out.append("".join(line))
        elif el.tag == _W + "tbl":
            for row in el.iter(_W + "tr"):
                cells = ["".join(t.text or "" for t in c.iter(_W + "t")).strip() for c in row.iter(_W + "tc")]
                out.append("\t".join(cells))
    text = "\n".join(out)
    return text.replace("\n" + PAGE_BREAK + "\n", PAGE_BREAK)


def _clip(text: str) -> str:
    return text.strip()[:MAX_CHARS]


def extract_text(filename: str, mime: str | None, data: bytes, lang: str = "vi") -> Extracted:
    if len(data) > MAX_BYTES:
        raise UnsupportedDocument(MESSAGES["too_large"][lang], 413)
    kind = _kind(filename, mime)
    if kind is None:
        raise UnsupportedDocument(MESSAGES["unsupported"][lang], 415)

    if kind == PDF:
        if not data.startswith(b"%PDF-"):
            raise UnsupportedDocument(MESSAGES["unsupported"][lang], 415)
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            text = PAGE_BREAK.join((p.extract_text() or "").strip() for p in reader.pages)
            pages = len(reader.pages)
        except Exception as e:
            raise UnsupportedDocument(MESSAGES["no_text"][lang]) from e
        method = "pdf-text"
    else:
        try:
            text = _docx_text(data)
        except Exception as e:
            raise UnsupportedDocument(MESSAGES["unsupported"][lang], 415) from e
        pages, method = count_pages(text), "docx"

    if len(text.replace(PAGE_BREAK, "").strip()) < MIN_TEXT_CHARS:
        raise UnsupportedDocument(MESSAGES["no_text"][lang])
    return Extracted(_clip(text), pages, method)
