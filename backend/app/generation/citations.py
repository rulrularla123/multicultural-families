"""답변 본문의 [n] 표시와 인용 목록을 맞춘다.

모델이 본문 번호와 인용 목록 순서를 어긋나게 쓰는 경우가 있어서, 인용마다 받은 marker(본문 번호)로 짝을 짓고
본문에 처음 나온 순서대로 1부터 다시 번호를 매긴다. 본문에서 쓰지 않은 인용은 버린다.
"""

import re
from typing import TypeVar

T = TypeVar("T")
_MARKER = re.compile(r"\[(\d+)\]")


def alignment_errors(answer: str, markers: list[int]) -> list[str]:
    """번호 정리 전에 누락·중복을 검사한다. 표시만 지워 근거 없는 문장을 남기지 않는다."""
    used = {int(m.group(1)) for m in _MARKER.finditer(answer)}
    available = set(markers)
    errors = []
    if not used:
        errors.append("The answer has no citation markers.")
    if missing := used - available:
        errors.append(f"Citation markers without sources: {sorted(missing)}")
    if duplicates := {n for n in markers if markers.count(n) > 1}:
        errors.append(f"Ambiguous duplicate citation markers: {sorted(duplicates)}")
    return errors


def align_citations(answer: str, citations: list[tuple[int, T]]) -> tuple[str, list[T]]:
    """citations: [(marker, 인용)] → (번호를 다시 매긴 본문, 본문 순서대로 정렬한 인용).

    같은 marker가 여러 번 오면 앞의 것을 쓴다. 본문에 있는데 맞는 인용이 없는 표시는 지운다.
    """
    by_marker: dict[int, T] = {}
    for marker, item in citations:
        by_marker.setdefault(marker, item)

    order: list[int] = []
    for m in _MARKER.finditer(answer):
        n = int(m.group(1))
        if n in by_marker and n not in order:
            order.append(n)
    renum = {old: new for new, old in enumerate(order, start=1)}

    def repl(m: re.Match) -> str:
        n = int(m.group(1))
        return f"[{renum[n]}]" if n in renum else ""

    text = _MARKER.sub(repl, answer)
    text = re.sub(r"[ \t]+([.,;:!?)])", r"\1", text)  # 지운 표시 앞에 남은 공백
    return text, [by_marker[n] for n in order]
