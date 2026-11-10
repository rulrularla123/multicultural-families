"""한국 법령 본문을 계층 트리로 파싱한다.

편 › 장 › 절 › 관 › 조(제10조의2) › 항(①) › 호(1. / 10의2.) › 목(가.)

입력은 legalize-kr 형식의 마크다운 본문(머리말 제외)이다.
  ## 제4장 외국인의 체류와 출국
  ### 제1절 외국인의 체류
  ##### 제25조 (체류기간 연장허가)
  **①** 외국인이 … <개정 2014.3.18>
    1\\. …            (호: 앞 공백 1~3칸)
      가\\. …          (목: 앞 공백 3칸 이상)
`## 부칙`부터는 부칙이라 파싱하지 않는다.
ID 규칙: '{법령ID}:J{조}:H{항}:O{호}:M{목}'  예) '출입국관리법:J25', '출입국관리법:J10-2:H1:O3'
"""

import re
from dataclasses import dataclass, field

from ingest.nlp.normalize import unescape_markdown

_HEAD = r"^#{1,6}\s*"
PYEON = re.compile(_HEAD + r"제(\d+)편(?:의(\d+))?\s*(.*)$")
JANG = re.compile(_HEAD + r"제(\d+)장(?:의(\d+))?\s*(.*)$")
JEOL = re.compile(_HEAD + r"제(\d+)절(?:의(\d+))?\s*(.*)$")
GWAN = re.compile(_HEAD + r"제(\d+)관(?:의(\d+))?\s*(.*)$")
JO = re.compile(_HEAD + r"제(\d+)조(?:의(\d+))?\s*(?:\(([^)]*)\))?\s*(.*)$")
ADDENDA = re.compile(_HEAD + r"부\s*칙")
TITLE = re.compile(r"^#\s+\S")
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳㉑㉒㉓㉔㉕㉖㉗㉘㉙㉚㉛㉜㉝㉞㉟"
HANG = re.compile(r"^(?:\*\*)?([" + CIRCLED + r"])(?:\*\*)?\s*(.*)$")
HO = re.compile(r"^( {1,3}|\t)(\d+)(?:의(\d+))?\\?\.\s*(.*)$")
MOK = re.compile(r"^( {3,}|\t\t)([가-힣])\\?\.\s*(.*)$")
AMEND_NOTE = re.compile(r"\s*<(?:개정|신설|전문개정|제목개정|본조신설|종전)[^>]*>\s*$")

LEVELS = ("pyeon", "jang", "jeol", "gwan", "jo", "hang", "ho", "mok")
_SECTION_UNITS = {"pyeon": "편", "jang": "장", "jeol": "절", "gwan": "관"}
_SECTION_PARENTS = {"pyeon": (), "jang": ("pyeon",), "jeol": ("jang", "pyeon"), "gwan": ("jeol", "jang", "pyeon")}


def _num(main: str, branch: str | None) -> str:
    """'10', '2' → '10의2' (표시용 번호)"""
    return f"{main}의{branch}" if branch else main


def _ko_num(number: str, unit: str) -> str:
    """'10의2' + '조' → '제10조의2' (법령 표기)"""
    main, _, branch = number.partition("의")
    return f"제{main}{unit}" + (f"의{branch}" if branch else "")


def _id_num(number: str) -> str:
    """'10의2' → '10-2' (ID용)"""
    return number.replace("의", "-")


@dataclass
class Node:
    level: str
    number: str
    heading: str = ""
    text: str = ""
    children: list["Node"] = field(default_factory=list)
    id: str = ""
    parent: "Node | None" = field(default=None, repr=False)
    ordinal: int = 0

    def add_text(self, line: str) -> None:
        self.text = f"{self.text}\n{line}" if self.text else line

    def label(self) -> str:
        if self.level in _SECTION_UNITS:
            return _ko_num(self.number, _SECTION_UNITS[self.level]) + (f" {self.heading}" if self.heading else "")
        if self.level == "jo":
            return _ko_num(self.number, "조") + (f"({self.heading})" if self.heading else "")
        if self.level == "hang":
            return f"제{self.number}항"
        if self.level == "ho":
            return _ko_num(self.number, "호")
        return f"{self.number}목"

    def render(self) -> str:
        """조문 전체 텍스트(하위 항·호·목 포함). 검색 청크와 인용 검증에 쓴다."""
        if self.level == "hang":
            head = f"{CIRCLED[int(self.number) - 1]} {self.text}".rstrip()
        elif self.level == "ho":
            head = f"{self.number}. {self.text}".rstrip()
        elif self.level == "mok":
            head = f"{self.number}. {self.text}".rstrip()
        else:
            head = self.label()
        parts = [head]
        if self.level not in ("hang", "ho", "mok") and self.text:
            parts.append(self.text)
        parts.extend(c.render() for c in self.children)
        return "\n".join(p for p in parts if p)

    def jo(self) -> "Node | None":
        n: Node | None = self
        while n is not None and n.level != "jo":
            n = n.parent
        return n

    def path(self, doc_title: str) -> str:
        chain: list[str] = []
        n: Node | None = self
        while n is not None:
            chain.append(n.label())
            n = n.parent
        return " › ".join([doc_title, *reversed(chain)])

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    @property
    def deleted(self) -> bool:
        return self.level == "jo" and not self.children and self.text.startswith("삭제")


@dataclass
class ParsedDocument:
    doc_id: str
    title: str
    roots: list[Node]
    preamble: str
    warnings: list[str]

    def nodes(self):
        for r in self.roots:
            yield from r.walk()

    def jos(self) -> list[Node]:
        return [n for n in self.nodes() if n.level == "jo"]


def _clean_heading(text: str) -> str:
    return AMEND_NOTE.sub("", text).strip()


def parse_law(text: str, doc_id: str, title: str) -> ParsedDocument:
    roots: list[Node] = []
    stack: dict[str, Node | None] = {lvl: None for lvl in LEVELS}
    preamble: list[str] = []
    ordinal = 0

    def attach(node: Node, parent_levels: tuple[str, ...]) -> None:
        nonlocal ordinal
        ordinal += 1
        node.ordinal = ordinal
        parent = next((stack[p] for p in parent_levels if stack[p] is not None), None)
        node.parent = parent
        (parent.children if parent else roots).append(node)
        for lvl in LEVELS[LEVELS.index(node.level):]:
            stack[lvl] = None
        stack[node.level] = node

    for raw in text.split("\n"):
        if not raw.strip():
            continue
        line = raw.strip()
        if ADDENDA.match(line):
            break
        if TITLE.match(line) and stack["jo"] is None and not roots:
            continue  # "# 출입국관리법" 법령 제목

        matched_section = False
        for level, pattern in (("pyeon", PYEON), ("jang", JANG), ("jeol", JEOL), ("gwan", GWAN)):
            if m := pattern.match(line):
                attach(Node(level, _num(m.group(1), m.group(2)), heading=_clean_heading(m.group(3))),
                       _SECTION_PARENTS[level])
                matched_section = True
                break
        if matched_section:
            continue
        if m := JO.match(line):
            node = Node("jo", _num(m.group(1), m.group(2)), heading=(m.group(3) or "").strip())
            if m.group(4).strip():
                node.add_text(unescape_markdown(m.group(4).strip()))
            attach(node, ("gwan", "jeol", "jang", "pyeon"))
            continue

        cur_jo = stack["jo"]
        if cur_jo is None:
            preamble.append(unescape_markdown(line))
            continue
        if m := HANG.match(line):
            attach(Node("hang", str(CIRCLED.index(m.group(1)) + 1), text=unescape_markdown(m.group(2).strip())),
                   ("jo",))
            continue
        if m := MOK.match(raw):
            parent = stack["ho"]
            if parent is not None:
                attach(Node("mok", m.group(2), text=unescape_markdown(m.group(3).strip())), ("ho",))
                continue
        if m := HO.match(raw):
            attach(Node("ho", _num(m.group(2), m.group(3)), text=unescape_markdown(m.group(4).strip())),
                   ("hang", "jo"))
            continue
        # 이어지는 문단 → 가장 깊은 현재 노드에 붙인다
        deepest = stack["mok"] or stack["ho"] or stack["hang"] or cur_jo
        deepest.add_text(unescape_markdown(line))

    doc = ParsedDocument(doc_id, title, roots, "\n".join(preamble), [])
    _assign_ids(doc)
    doc.warnings = validate(doc)
    return doc


_PREFIX = {"pyeon": "P", "jang": "C", "jeol": "S", "gwan": "G"}


def _assign_ids(doc: ParsedDocument) -> None:
    used: set[str] = set()
    for n in doc.nodes():
        if n.level in _PREFIX:
            parent = n.parent.id if n.parent else doc.doc_id
            n.id = f"{parent}:{_PREFIX[n.level]}{_id_num(n.number)}"
        elif n.level == "jo":
            n.id = f"{doc.doc_id}:J{_id_num(n.number)}"
        elif n.level == "hang":
            n.id = f"{n.parent.id}:H{n.number}"
        elif n.level == "ho":
            n.id = f"{n.parent.id}:O{_id_num(n.number)}"
        else:
            n.id = f"{n.parent.id}:M{n.number}"
        base, k = n.id, 2
        while n.id in used:
            n.id = f"{base}_{k}"
            k += 1
        used.add(n.id)


def validate(doc: ParsedDocument) -> list[str]:
    """조 번호 중복·누락, 빈 조문 등 파싱 이상을 보고한다."""
    warnings: list[str] = []
    jos = doc.jos()
    if not jos:
        return ["조를 하나도 찾지 못함: 원문 형식을 확인하세요"]
    ids = [j.id for j in jos]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        warnings.append(f"중복 조: {sorted(dup)}")
    mains = sorted({int(j.number.split("의")[0]) for j in jos})
    missing = sorted(set(range(mains[0], mains[-1] + 1)) - set(mains))
    if missing:
        warnings.append(f"누락된 조 번호: {missing[:20]}{' …' if len(missing) > 20 else ''}")
    empty = [j.number for j in jos if not j.text and not j.children]
    if empty:
        warnings.append(f"본문이 빈 조: {empty[:20]}")
    return warnings
