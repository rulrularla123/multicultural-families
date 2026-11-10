import pytest

from app.documents.extract import DOCX, MAX_BYTES, PDF, UnsupportedDocument, extract_text


def test_docx_sample(demo_dir):
    e = extract_text("a.docx", DOCX, (demo_dir / "sample-extension-guide.docx").read_bytes())
    assert e.method == "docx" and "체류기간 만료일" in e.text


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
