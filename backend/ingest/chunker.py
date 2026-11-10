"""조 단위 청크. 긴 조는 항 단위로 나누고 경로 헤더를 붙인다. 삭제된 조는 넣지 않는다."""

from dataclasses import dataclass

from ingest.nlp.tokenize import to_index_text
from ingest.parsers.structure import Node, ParsedDocument

MAX_CHARS = 2000  # 한국어 기준 대략 1,300토큰


@dataclass
class ChunkDraft:
    provision_id: str
    jo_id: str
    content: str
    tokens: str


def chunk_document(doc: ParsedDocument) -> list[ChunkDraft]:
    out: list[ChunkDraft] = []
    for jo in doc.jos():
        if jo.deleted:
            continue
        path = jo.path(doc.title)
        body = jo.render()
        if len(body) <= MAX_CHARS:
            out.append(_draft(jo, jo, path, body))
            continue
        if not jo.children:
            # 항이 없는 긴 조(개정 문구를 통째로 인용한 조 등)는 줄 단위로 창을 나눈다
            for n, part in enumerate(_windows(body), 1):
                out.append(_draft(jo, jo, f"{path} ({n})", part))
            continue
        # 항마다 조 도입문을 붙이되, 개정 법률처럼 도입문이 긴 경우는 잘라서 모든 청크가 같은 단어로 부풀지 않게 한다
        intro_text = jo.text if len(jo.text) <= 300 else jo.text[:300].rsplit(" ", 1)[0] + " …"
        intro = jo.label() + (f"\n{intro_text}" if intro_text else "")
        for hang in jo.children:
            kpath = f"{path} › {hang.label()}"
            parts = _windows(hang.render())
            for n, part in enumerate(parts, 1):
                label = kpath if len(parts) == 1 else f"{kpath} ({n})"
                out.append(_draft(hang, jo, label, f"{intro}\n{part}", index_text=f"{jo.label()}\n{part}"))
    return out


def _windows(body: str) -> list[str]:
    parts, cur = [], ""
    for line in body.split("\n"):
        if cur and len(cur) + len(line) > MAX_CHARS:
            parts.append(cur)
            cur = ""
        cur = f"{cur}\n{line}" if cur else line[: MAX_CHARS * 2]
    if cur:
        parts.append(cur)
    return parts


def _draft(node: Node, jo: Node, path: str, body: str, index_text: str | None = None) -> ChunkDraft:
    # 검색 토큰: 조 제목 + (항 청크는 항 본문만, 조 청크는 전체). 도입문 반복으로 점수가 부풀지 않게 한다
    index_body = index_text or body
    return ChunkDraft(
        provision_id=node.id,
        jo_id=jo.id,
        content=f"[{path}]\n{body}",
        tokens=to_index_text(f"{jo.heading}\n{index_body}"),
    )
