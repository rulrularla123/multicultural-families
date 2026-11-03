"""US-02 인수 조건 5·6: 추출 실패를 LLM 입력으로 전달하지 않는다."""
import importlib.util
import unittest
from io import BytesIO

from app.common.pdf_extraction import ExtractionFailure, extract_pdf


class SignatureTests(unittest.TestCase):
    def test_non_pdf_rejected_without_parser(self):
        result = extract_pdf("sample.pdf", b"not a PDF")
        self.assertEqual(result.failure, ExtractionFailure.INVALID_PDF)
        self.assertEqual(result.pages, ())


@unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf 설치 필요")
class PdfTests(unittest.TestCase):
    def make_pdf(self, texts, password=None):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter()
        for text in texts:
            page = writer.add_blank_page(width=200, height=200)
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                     NameObject("/Subtype"): NameObject("/Type1"),
                                     NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
        if password:
            writer.encrypt(password)
        output = BytesIO()
        writer.write(output)
        return output.getvalue()

    def test_pages_retain_names_numbers_and_text(self):
        result = extract_pdf("mock.pdf", self.make_pdf(["first", "second"]))
        self.assertTrue(result.ok)
        self.assertEqual([(p.file_name, p.page, p.text.strip()) for p in result.pages],
                         [("mock.pdf", 1, "first"), ("mock.pdf", 2, "second")])

    def test_empty_page_discards_partial_result(self):
        result = extract_pdf("mock.pdf", self.make_pdf(["first", ""]))
        self.assertEqual(result.failure, ExtractionFailure.NO_TEXT)
        self.assertEqual(result.failed_page, 2)
        self.assertEqual(result.pages, ())

    def test_encrypted_pdf_rejected(self):
        result = extract_pdf("mock.pdf", self.make_pdf(["sample"], "test-only"))
        self.assertEqual(result.failure, ExtractionFailure.ENCRYPTED)

    def test_broken_pdf_rejected(self):
        self.assertEqual(extract_pdf("mock.pdf", b"%PDF-1.4 broken").failure,
                         ExtractionFailure.INVALID_PDF)
