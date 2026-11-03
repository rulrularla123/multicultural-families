"""US-02 LLM 모의 응답 fixture 점검 (2단계 US-02·03 인수 테스트 준비).

기준: backlog.md US-02 인수 조건, app/common/llm_client.py(#80, 이주환)의 공개 함수만 쓴다.
DB·서버 상태 전이는 다루지 않는다(김민건 US-02 서버와 API.md 점검 항목 뒤에 따로 쓴다).
llm_client가 main에 없으면 이 파일 전체를 건너뛴다.
"""
import asyncio

import pytest

llm = pytest.importorskip("app.common.llm_client")


def run(coro):
    return asyncio.run(coro)


def failure_of(check_input, transport, **kw):
    with pytest.raises(llm.CheckClientError) as caught:
        run(llm.check_documents(check_input, transport, **kw))
    return caught.value.code


def test_us02_mock_success_returns_items_with_registered_criterion(check_input, llm_transport):
    """US-02 (정상) 2: 결과 항목마다 근거 기준 ID가 있으면 확인 필요가 아니다."""
    result = run(llm.check_documents(check_input, llm_transport("success")))

    items = result.cautions + result.possible_omissions + result.additional_documents
    assert items
    assert all(item.criterion_id == "mock-criterion-1" and not item.needs_confirmation for item in items)


def test_us02_llm_error_is_check_failure(check_input, llm_transport):
    """US-02 (실패) 6: LLM 호출 오류 → 자동 점검 실패 사유(transport_error)."""
    assert failure_of(check_input, llm_transport("error")) == llm.ClientFailure.TRANSPORT


def test_us02_llm_over_time_limit_is_timeout(check_input, llm_transport):
    """US-02 (실패) 6: 시간 제한 초과 → timeout. 60초 대신 짧은 제한을 넣어 같은 경로를 확인한다."""
    assert failure_of(check_input, llm_transport("delay", delay=1), timeout=0.05) == llm.ClientFailure.TIMEOUT


def test_us02_time_limit_cannot_exceed_60_seconds(check_input, llm_transport):
    """US-02 미확정 60초(팀 설계값): 60초보다 긴 제한은 받지 않는다."""
    with pytest.raises(ValueError):
        run(llm.check_documents(check_input, llm_transport("success"), timeout=61))


def test_us02_malformed_llm_response_is_invalid_response(check_input, llm_transport):
    """US-02 (실패) 6 / PRD 7절: 응답 형식 오류 → invalid_response, 결과로 쓰지 않는다."""
    assert failure_of(check_input, llm_transport("invalid")) == llm.ClientFailure.INVALID_RESPONSE


@pytest.mark.parametrize("criterion_id", [None, "not-sent-criterion"], ids=["missing", "unknown"])
def test_us02_item_without_registered_criterion_needs_confirmation(check_input, llm_fixed_response, criterion_id):
    """US-02 (정상) 2: 근거 기준 ID가 없는 항목은 확인 필요. 전달하지 않은 ID도 믿지 않는다."""
    transport = llm_fixed_response({
        "cautions": [{"text": "근거 확인이 필요한 모의 항목", "criterion_id": criterion_id}],
        "possible_omissions": [], "additional_documents": [],
    })

    result = run(llm.check_documents(check_input, transport))
    assert result.cautions[0].criterion_id is None
    assert result.cautions[0].needs_confirmation


def test_us02_request_body_has_no_account_id_filename_or_pdf_binary(check_input, llm_transport):
    """US-02 (LLM) 11: 요청 본문에 계정 ID·PDF 원본이 없고, 허용된 항목만 간다."""
    transport = llm_transport("success")
    run(llm.check_documents(check_input, transport))

    assert len(transport.payloads) == 1
    assert set(transport.payloads[0]) == {"situation", "document_texts", "support_type", "criteria"}
    sent = transport.sent_text
    for forbidden in ("demo-user-1", "demo-user-2", "demo-officer", "%PDF", ".pdf"):
        assert forbidden not in sent


@pytest.mark.parametrize("where", ["situation", "document"])
@pytest.mark.parametrize("value", ["010-1234-5678", "01012345678"], ids=["hyphen", "no-hyphen"])
def test_us02_identifying_pattern_blocks_llm_call(llm, check_input, llm_transport, where, value):
    """US-02 (실패) 5·(LLM) 11: 식별정보 패턴이 있으면 LLM을 호출하지 않는다."""
    if where == "situation":
        request = check_input.model_copy(update={"situation": f"연락처는 {value}입니다."})
    else:
        request = check_input.model_copy(update={"document_texts": (f"모의 서류 연락처 {value}",)})
    transport = llm_transport("success")

    assert failure_of(request, transport) == llm.ClientFailure.IDENTIFYING_INPUT
    assert transport.payloads == []
