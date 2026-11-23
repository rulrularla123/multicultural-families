from app.common.identity_patterns import mask
from app.documents.extract import MAX_CHARS, PDF, extract_text


def document_payload(filename: str, mime: str, data: bytes, lang: str) -> dict:
    """Represent the browser's upload payload in tests of the server."""
    extracted = extract_text(filename, mime, data, lang)
    return {
        "text": mask(extracted.text)[0][:MAX_CHARS],
        "format": "pdf" if mime == PDF else "docx",
        "file_size": len(data),
        "page_count": extracted.page_count,
        "lang": lang,
    }
