from io import BytesIO

import pytest
from docx import Document

from app.documents.extract import DOCX, MAX_BYTES, PAGE_BREAK, PDF, UnsupportedDocument, extract_text


def test_docx_sample(demo_dir):
    e = extract_text("a.docx", DOCX, (demo_dir / "demo-extension-supplement-notice.docx").read_bytes())
    assert e.method == "docx" and "체류기간 만료일" in e.text


def test_docx_preserves_table_order_and_page_break():
    document = Document()
    document.add_paragraph("체류기간 연장을 위한 서류 안내입니다.")
    cells = document.add_table(rows=1, cols=2).rows[0].cells
    cells[0].text = "제출 서류"
    cells[1].text = "체류지 증명서"
    document.add_page_break()
    document.add_paragraph("두 번째 쪽에 추가 준비 사항이 있습니다.")
    buffer = BytesIO()
    document.save(buffer)

    extracted = extract_text("notice.docx", DOCX, buffer.getvalue(), "ko")

    assert extracted.page_count == 2
    first_page, second_page = extracted.text.split(PAGE_BREAK)
    assert first_page.strip().splitlines() == ["체류기간 연장을 위한 서류 안내입니다.", "제출 서류\t체류지 증명서"]
    assert second_page.strip() == "두 번째 쪽에 추가 준비 사항이 있습니다."


def test_valid_docx_without_text_is_422():
    buffer = BytesIO()
    Document().save(buffer)

    with pytest.raises(UnsupportedDocument, match="글자를 읽지 못했습니다") as error:
        extract_text("empty.docx", DOCX, buffer.getvalue(), "ko")

    assert error.value.status == 422


@pytest.mark.parametrize("name, mime, data, status", [
    ("a.pdf", PDF, b"not a pdf at all" * 10, 415),        # 확장자는 PDF지만 시그니처가 없음
    ("a.txt", "text/plain", b"hello" * 20, 415),
    ("a.pdf", PDF, b"%PDF-" + b"0" * MAX_BYTES, 413),     # 10,485,760바이트 초과
    ("a.docx", DOCX, b"PK broken", 415),
])
def test_rejects(name, mime, data, status):
    with pytest.raises(UnsupportedDocument) as e:
        extract_text(name, mime, data, "ko")
    assert e.value.status == status


def test_message_language():
    with pytest.raises(UnsupportedDocument) as e:
        extract_text("a.txt", "text/plain", b"x", "vi")
    assert "PDF" in str(e.value) and "Chỉ" in str(e.value)
