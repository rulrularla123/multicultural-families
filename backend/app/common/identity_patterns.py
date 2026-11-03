import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class IdentityKind(StrEnum):
    ALIEN_REGISTRATION = "외국인등록번호"
    PASSPORT = "여권번호"
    MOBILE_PHONE = "휴대전화번호"


class Source(StrEnum):
    SITUATION = "상황 설명"
    DOCUMENT = "서류"


@dataclass(frozen=True)
class PageText:
    file_name: str
    page: int
    text: str


@dataclass(frozen=True)
class Finding:
    kind: IdentityKind
    source: Source
    file_name: str | None = None
    page: int | None = None


# backlog.md "정상 흐름과 공통 조건"의 패턴만 쓴다. \d는 다른 문자 체계의 숫자도 잡아서 [0-9]로 쓴다.
PATTERNS = {
    IdentityKind.ALIEN_REGISTRATION: re.compile(r"(?<![0-9])[0-9]{6}-[0-9]{7}(?![0-9])"),
    IdentityKind.PASSPORT: re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{1,2}[0-9]{7,8}(?![A-Za-z0-9])"),
    IdentityKind.MOBILE_PHONE: re.compile(r"(?<![0-9])010-?[0-9]{4}-?[0-9]{4}(?![0-9])"),
}


def kinds_in(text: str) -> list[IdentityKind]:
    return [kind for kind, pattern in PATTERNS.items() if pattern.search(text)]


def find_identity_patterns(situation: str, pages: Sequence[PageText]) -> list[Finding]:
    """발견 위치와 종류만 돌려준다. 발견된 값은 결과에 넣지 않는다."""
    findings = [Finding(kind, Source.SITUATION) for kind in kinds_in(situation)]
    for page in pages:
        findings += [
            Finding(kind, Source.DOCUMENT, page.file_name, page.page) for kind in kinds_in(page.text)
        ]
    return findings
