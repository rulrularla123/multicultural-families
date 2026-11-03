"""US-02 (실패·거절) 식별정보 패턴 검사. 패턴은 backlog.md "정상 흐름과 공통 조건" 원문 기준."""

import pytest

from app.common.identity_patterns import (
    Finding,
    IdentityKind,
    PageText,
    Source,
    find_identity_patterns,
)


ARN = IdentityKind.ALIEN_REGISTRATION
PASSPORT = IdentityKind.PASSPORT
PHONE = IdentityKind.MOBILE_PHONE


def situation_kinds(text):
    return [finding.kind for finding in find_identity_patterns(text, [])]


@pytest.mark.parametrize(
    "text, kind",
    [
        ("등록번호는 123456-1234567입니다", ARN),
        ("여권 M12345678 사본", PASSPORT),
        ("여권 AB1234567 사본", PASSPORT),
        ("여권 m1234567 사본", PASSPORT),
        ("연락처 010-1234-5678", PHONE),
        ("연락처 01012345678", PHONE),
        ("연락처 010-12345678", PHONE),
        ("여권M12345678입니다", PASSPORT),
    ],
)
def test_pattern_in_situation_is_found(text, kind):
    assert situation_kinds(text) == [kind]


@pytest.mark.parametrize(
    "text",
    [
        "12345-1234567",
        "1234567-1234567",
        "123456-123456",
        "123456-12345678",
        "M123456",
        "M123456789",
        "ABC1234567",
        "011-1234-5678",
        "010-123-5678",
        "010-1234-56789",
        "9010-1234-5678",
        "체류기간 연장을 위해 준비한 서류를 확인하고 싶습니다.",
        "",
    ],
)
def test_text_outside_patterns_is_not_found(text):
    assert situation_kinds(text) == []


def test_document_finding_has_file_name_and_page():
    pages = [
        PageText("혼인관계증명서.pdf", 1, "모의 서류입니다"),
        PageText("혼인관계증명서.pdf", 2, "연락처 010-1234-5678"),
    ]

    assert find_identity_patterns("상황 설명", pages) == [
        Finding(PHONE, Source.DOCUMENT, "혼인관계증명서.pdf", 2)
    ]


def test_situation_and_document_findings_are_separated():
    pages = [PageText("모의.pdf", 1, "여권 M12345678")]

    assert find_identity_patterns("등록번호 123456-1234567", pages) == [
        Finding(ARN, Source.SITUATION),
        Finding(PASSPORT, Source.DOCUMENT, "모의.pdf", 1),
    ]


def test_same_kind_in_same_place_is_reported_once():
    assert situation_kinds("010-1111-2222 또는 010-3333-4444") == [PHONE]


def test_findings_do_not_contain_found_value():
    findings = find_identity_patterns(
        "123456-1234567", [PageText("모의.pdf", 1, "01012345678")]
    )

    for finding in findings:
        assert "123456" not in repr(finding)
        assert "01012345678" not in repr(finding)
