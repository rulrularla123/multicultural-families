"""US-02: 전송 경계, 형식 검사, 시간 제한. 실제 외부 호출 없음."""
import asyncio
from datetime import date
import json
import unittest

import httpx
from pydantic import ValidationError

from app.common.llm_client import (
    Analysis, CheckClientError, CheckInput, ClientFailure, CriterionInput,
    GeminiTransport, MockTransport, build_payload, check_documents,
)


def request():
    return CheckInput(situation="모의 서류 점검", document_texts=("모의 텍스트",),
                      criteria=(CriterionInput(criterion_id="mock-rule", body="모의 기준",
                                               source="모의 출처", checked_on=date(2026, 11, 3)),))


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_has_evidence(self):
        result = await check_documents(request(), MockTransport())
        self.assertFalse(result.cautions[0].needs_confirmation)

    async def test_unknown_or_null_evidence_requires_confirmation(self):
        class Unknown:
            async def generate(self, payload):
                return json.dumps({"cautions": [{"text": "확인", "criterion_id": "unknown"},
                                                 {"text": "확인", "criterion_id": None}],
                                   "possible_omissions": [], "additional_documents": []})
        result = await check_documents(request(), Unknown())
        self.assertTrue(all(x.needs_confirmation for x in result.cautions))

    async def test_errors_are_sanitized(self):
        for mode, expected in [("error", ClientFailure.TRANSPORT),
                               ("invalid", ClientFailure.INVALID_RESPONSE),
                               ("delay", ClientFailure.TIMEOUT)]:
            with self.subTest(mode=mode), self.assertRaises(CheckClientError) as caught:
                await check_documents(request(), MockTransport(mode), timeout=0.01)
            self.assertEqual(caught.exception.code, expected)
            self.assertEqual(str(caught.exception), expected.value)

    async def test_identifying_input_never_reaches_transport(self):
        class Never:
            async def generate(self, payload):
                raise AssertionError("must not be called")
        for value in ["010-1234-5678", "123456-1234567", "AB1234567"]:
            with self.subTest(value=value), self.assertRaises(CheckClientError) as caught:
                await check_documents(request().model_copy(update={"situation": value}), Never())
            self.assertEqual(caught.exception.code, ClientFailure.IDENTIFYING_INPUT)

    async def test_identifying_document_and_criterion_blocked(self):
        for field, value in [("document_texts", ("01012345678",)),
                             ("criteria", (request().criteria[0].model_copy(update={"body": "01012345678"}),))]:
            with self.subTest(field=field), self.assertRaises(CheckClientError) as caught:
                await check_documents(request().model_copy(update={field: value}), MockTransport())
            self.assertEqual(caught.exception.code, ClientFailure.IDENTIFYING_INPUT)

    async def test_timeout_cancels_late_work(self):
        cancelled = asyncio.Event()
        class Slow:
            async def generate(self, payload):
                try:
                    await asyncio.sleep(10)
                finally:
                    cancelled.set()
        with self.assertRaises(CheckClientError):
            await check_documents(request(), Slow(), timeout=0.01)
        self.assertTrue(cancelled.is_set())

    async def test_timeout_cannot_exceed_sixty(self):
        for timeout in [0, 61]:
            with self.assertRaises(ValueError):
                await check_documents(request(), MockTransport(), timeout=timeout)

    async def test_gemini_wire_payload_and_schema_without_live_call(self):
        def handle(req):
            self.assertEqual(req.url.path, "/v1beta/models/test-model:generateContent")
            self.assertEqual(req.headers["x-goog-api-key"], "test-key")
            body = json.loads(req.content)
            payload = json.loads(body["contents"][0]["parts"][0]["text"])
            self.assertEqual(set(payload), {"situation", "document_texts", "support_type", "criteria"})
            self.assertNotIn("file_name", req.content.decode())
            self.assertIn("responseJsonSchema", body["generationConfig"])
            return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {
                "parts": [{"text": '{"cautions": [], "possible_omissions": [], "additional_documents": []}'}]}}]})
        result = await check_documents(request(), GeminiTransport(api_key="test-key", model="test-model",
                                                                 http_transport=httpx.MockTransport(handle)))
        self.assertEqual(result.cautions, [])

    async def test_gemini_bad_envelopes_fail(self):
        for status, body, expected in [(503, {}, ClientFailure.TRANSPORT),
                                       (200, {}, ClientFailure.INVALID_RESPONSE),
                                       (200, {"candidates": [{"finishReason": "MAX_TOKENS"}]}, ClientFailure.INVALID_RESPONSE)]:
            with self.subTest(status=status, body=body), self.assertRaises(CheckClientError) as caught:
                await check_documents(request(), GeminiTransport(api_key="test-key", model="test-model",
                    http_transport=httpx.MockTransport(lambda req: httpx.Response(status, json=body))))
            self.assertEqual(caught.exception.code, expected)

    def test_no_internal_fields_or_original_pdf_allowed(self):
        with self.assertRaises(ValidationError):
            CheckInput(**{**request().model_dump(), "owner_id": "account"})
        with self.assertRaises(ValidationError):
            CheckInput(**{**request().model_dump(), "document_texts": (b"%PDF-original",)})

    def test_blank_input_rejected(self):
        with self.assertRaises(CheckClientError):
            build_payload(request().model_copy(update={"situation": "  "}))

    def test_response_must_have_all_groups_and_no_state_field(self):
        for data in [{}, {"cautions": [], "possible_omissions": [], "additional_documents": [], "status": "승인"}]:
            with self.assertRaises(ValidationError):
                Analysis.model_validate(data)
