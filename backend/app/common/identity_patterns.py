"""식별정보 패턴 찾기·마스킹. LLM에 보내기 전에 질문과 서류 추출 텍스트에서 값을 지운다.

패턴은 번호 형식만 본다. 실명·주소는 잡지 못하므로 화면에서 모의 서류 사용을 안내한다.
  외국인등록번호·주민등록번호: 숫자 6자리-7자리 (하이픈 생략 13자리 포함)
  여권번호: 영문 1~2자 + 숫자 7~8자
  휴대전화번호: 010-4자리-4자리 (하이픈·공백 생략 포함)
"""

import re
from enum import StrEnum


class IdentityKind(StrEnum):
    REGISTRATION = "registration_number"
    PASSPORT = "passport_number"
    MOBILE_PHONE = "mobile_phone"


# \\d는 다른 문자 체계의 숫자도 잡아서 [0-9]로 쓴다
PATTERNS = {
    IdentityKind.REGISTRATION: re.compile(r"(?<![0-9])[0-9]{6}\s?-?\s?[1-8][0-9]{6}(?![0-9])"),
    IdentityKind.PASSPORT: re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{1,2}[0-9]{7,8}(?![A-Za-z0-9])"),
    IdentityKind.MOBILE_PHONE: re.compile(r"(?<![0-9])010[\s-]?[0-9]{4}[\s-]?[0-9]{4}(?![0-9])"),
}

PLACEHOLDER = {
    IdentityKind.REGISTRATION: "[등록번호 가림]",
    IdentityKind.PASSPORT: "[여권번호 가림]",
    IdentityKind.MOBILE_PHONE: "[전화번호 가림]",
}


def find_kinds(text: str) -> list[IdentityKind]:
    return [kind for kind, pattern in PATTERNS.items() if pattern.search(text)]


def mask(text: str) -> tuple[str, int]:
    """(마스킹한 텍스트, 가린 개수). 가린 값은 어디에도 남기지 않는다."""
    count = 0
    for kind, pattern in PATTERNS.items():
        text, n = pattern.subn(PLACEHOLDER[kind], text)
        count += n
    return text, count
