"""업로드 문서를 조항(또는 문단) 단위로 나눈다. 각 조항은 C1, C2 … ID와 걸쳐 있는 쪽 번호를 갖는다."""

import re
from dataclasses import dataclass, field

from app.documents.extract import PAGE_BREAK

# 조항 제목으로 보는 줄: 제5조 / Điều 5 / Article 5
STRONG = re.compile(r"^\s*제\s*\d+\s*조|^\s*(Điều|ĐIỀU|Article|ARTICLE)\s+\d+")
# 약한 제목: 1. / 1) / 가. / ① / I. (안내문·통지서의 항목 번호)
WEAK = re.compile(r"^\s*([IVX]{1,5}\.|\d{1,2}[.)]|[가-하][.)]|[①-⑳]|[□■○●※])\s*\S")
MAX_SEGMENTS = 60
PARA_CHARS = 900

Line = tuple[int, str]  # (쪽 번호, 줄)


@dataclass
class Segment:
    id: str
    title: str
    text: str
    pages: list[int] = field(default_factory=lambda: [1])


def _split(lines: list[Line], pattern: re.Pattern) -> list[list[Line]]:
    groups: list[list[Line]] = []
    preamble: list[Line] = []
    for line in lines:
        if pattern.match(line[1]):
            groups.append([line])
        elif groups:
            groups[-1].append(line)
        else:
            preamble.append(line)
    if preamble and groups:
        groups.insert(0, preamble)
    return groups


def _by_paragraph(lines: list[Line]) -> list[list[Line]]:
    groups: list[list[Line]] = [[]]
    size = 0
    for line in lines:
        s = line[1]
        if size > PARA_CHARS and (not s.strip() or s.rstrip().endswith((".", ":", ";"))):
            groups.append([])
            size = 0
        groups[-1].append(line)
        size += len(s)
    return [g for g in groups if "".join(s for _, s in g).strip()]


def _lines(text: str) -> list[Line]:
    out: list[Line] = []
    for page_no, page in enumerate(text.replace("\r", "").split(PAGE_BREAK), start=1):
        out.extend((page_no, ln.rstrip()) for ln in page.split("\n"))
    return out


def segment_document(text: str) -> list[Segment]:
    lines = _lines(text)
    groups = _split(lines, STRONG)
    if len(groups) < 3:
        groups = _split(lines, WEAK)
    if len(groups) < 3:
        groups = _by_paragraph(lines)

    # 너무 잘게 나뉘면 이웃끼리 합친다
    while len(groups) > MAX_SEGMENTS:
        merged = []
        for i in range(0, len(groups), 2):
            merged.append(groups[i] + (groups[i + 1] if i + 1 < len(groups) else []))
        groups = merged

    segments = []
    for g in groups:
        body = "\n".join(s for _, s in g).strip()
        if not body:
            continue
        first = next((s.strip() for _, s in g if s.strip()), "")
        title = first if len(first) <= 90 else first[:87] + "…"
        # 빈 줄만 걸친 쪽은 빼고, 글자가 있는 쪽만 남긴다
        pages = sorted({p for p, s in g if s.strip()})
        segments.append(Segment(f"C{len(segments) + 1}", title, body, pages or [g[0][0]]))
    return segments
