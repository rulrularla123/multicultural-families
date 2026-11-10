"""조문 본문에서 다른 조문을 가리키는 표현을 규칙 기반으로 추출한다.

처리하는 표현 예:
  - "제46조제1항 각 호"                      → 같은 문서 J46:H1
  - "제4조제1항제3호"                        → J4:H1:O3
  - "제93조의2, 제93조의3"                   → J93-2, J93-3
  - "제94조부터 제99조까지"                  → J94 … J99
  - "제1항에 따른" (조 없이)                  → 현재 조의 H1
  - "이 조 제2항", "같은 조 제3항"            → 현재 조 / 바로 앞에서 말한 조
  - "「난민법」 제2조제1호"                   → 법령명으로 문서 해석 (미적재면 미해결)
  - "같은 법 제17조제1항"                    → 바로 앞 「」 법령
  - 시행령의 "법 제25조", 시행규칙의 "영 제31조" → 상위 법률·시행령
"""

import re
from dataclasses import dataclass

# 제25조 / 제10조의2 / 제46조제1항 / 제4조제1항제3호 / 제2조제17호가목
REF_RE = re.compile(
    r"제(?P<jo>\d+)조(?:의(?P<jo_b>\d+))?"
    r"(?:\s?제(?P<hang>\d+)항)?"
    r"(?:\s?제(?P<ho>\d+)호(?:의(?P<ho_b>\d+))?)?"
    r"(?:(?P<mok>[가-하])목)?"
)
RANGE_RE = re.compile(r"제(\d+)조(?:의\d+)?부터\s*제(\d+)조(?:의\d+)?까지")
# 조 없이 항·호만 쓴 참조: 현재 조(또는 현재 항) 안을 가리킨다
LOCAL_RE = re.compile(r"(?<![조항\d의])제(?P<hang>\d+)항(?:\s?제(?P<ho>\d+)호(?:의(?P<ho_b>\d+))?)?")
SAME_JO_RE = re.compile(r"(?:이|같은)\s?조\s?제(?P<hang>\d+)항(?:\s?제(?P<ho>\d+)호)?")
BRACKET_RE = re.compile(r"「([^」]+)」\s*$")
SAME_LAW_RE = re.compile(r"같은\s?법\s*$")
SELF_RE = re.compile(r"이\s?(?:법|영|규칙)\s*$")
PARENT_LAW_RE = re.compile(r"(?<![가-힣])법\s*$")
PARENT_DECREE_RE = re.compile(r"(?<![가-힣])영\s*$")

UNKNOWN_PREFIX = "?"


@dataclass(frozen=True)
class RawRef:
    jo: str                  # '25', '10-2'
    hang: str | None
    ho: str | None           # '3', '10-2'
    mok: str | None
    target_doc: str | None   # None = 같은 문서, '?난민법' = 미적재 외부 법령
    rel: str                 # REFERENCES (현행 통합본이라 개정 관계는 없다)
    evidence: str


class AliasIndex:
    """법령 이름(띄어쓰기 무시) → 문서 ID."""

    def __init__(self, aliases: dict[str, str]):
        self._aliases = {_key(k): v for k, v in aliases.items() if k.strip()}

    def get(self, name: str) -> str | None:
        return self._aliases.get(_key(name))


def _key(name: str) -> str:
    return re.sub(r"\s+", "", name)


@dataclass(frozen=True)
class DocContext:
    """참조 해석에 필요한 현재 문서 정보."""
    id: str
    parent_law: str | None = None     # 시행령·시행규칙의 "법"
    parent_decree: str | None = None  # 시행규칙의 "영"


def _branch(main: str, branch: str | None) -> str:
    return f"{main}-{branch}" if branch else main


def _doc_before(prefix: str, ctx: DocContext, aliases: AliasIndex, last_external: list[str]) -> str | None:
    """참조 바로 앞의 법령 표시로 대상 문서를 정한다. None이면 같은 문서."""
    if m := BRACKET_RE.search(prefix):
        name = m.group(1)
        doc = aliases.get(name) or UNKNOWN_PREFIX + name
        last_external[:] = [doc]
        return doc
    if SAME_LAW_RE.search(prefix):
        return last_external[0] if last_external else None
    if SELF_RE.search(prefix):
        return None
    if ctx.parent_decree and PARENT_DECREE_RE.search(prefix):
        return ctx.parent_decree
    if ctx.parent_law and PARENT_LAW_RE.search(prefix):
        return ctx.parent_law
    return None


_JOINER = re.compile(r"\s*(?:,|및|또는|ㆍ|·|와|과)\s*")


def extract_refs(text: str, ctx: DocContext, aliases: AliasIndex) -> list[RawRef]:
    refs: list[RawRef] = []
    for line in text.split("\n"):
        last_external: list[str] = []
        ranges = list(RANGE_RE.finditer(line))
        matches = [("range", m) for m in ranges]
        matches += [("ref", m) for m in REF_RE.finditer(line) if not any(r.start() <= m.start() < r.end() for r in ranges)]
        matches.sort(key=lambda x: x[1].start())

        prev_doc: str | None = None
        prev_end = -1
        for kind, m in matches:
            prefix = line[max(0, m.start() - 40) : m.start()]
            doc = _doc_before(prefix, ctx, aliases, last_external)
            # "「형법」 제127조 및 제129조부터 제132조까지"처럼 이어지는 참조는 앞의 법령을 물려받는다
            if doc is None and prev_end >= 0 and _JOINER.fullmatch(line[prev_end : m.start()]):
                doc = prev_doc
            if kind == "range":
                a, b = int(m.group(1)), int(m.group(2))
                if 0 < b - a <= 100:
                    refs.extend(RawRef(str(n), None, None, None, doc, "REFERENCES", m.group(0)) for n in range(a, b + 1))
            else:
                refs.append(RawRef(
                    _branch(m.group("jo"), m.group("jo_b")), m.group("hang"),
                    _branch(m.group("ho"), m.group("ho_b")) if m.group("ho") else None,
                    m.group("mok"), doc, "REFERENCES", m.group(0),
                ))
            prev_doc, prev_end = doc, m.end()
    return refs


def extract_local_refs(text: str) -> list[tuple[str, str | None, str]]:
    """조 없이 쓴 "제1항", "같은 조 제2항", "이 조 제3항제1호" → [(항, 호, 근거)] (현재 조 안)"""
    out: list[tuple[str, str | None, str]] = []
    for line in text.split("\n"):
        spans = [(m.start(), m.end()) for m in REF_RE.finditer(line)]
        for m in SAME_JO_RE.finditer(line):
            out.append((m.group("hang"), m.group("ho"), m.group(0)))
            spans.append((m.start(), m.end()))
        for m in LOCAL_RE.finditer(line):
            if any(s <= m.start() < e for s, e in spans):
                continue
            ho = _branch(m.group("ho"), m.group("ho_b")) if m.group("ho") else None
            out.append((m.group("hang"), ho, m.group(0)))
    return out
