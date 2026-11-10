"""문서에서 뽑은 사실(주장)과 사용자가 확인한 사실을 다룬다.

- 인테이크가 뽑은 사실은 source="document", confirmed=False 로 저장한다 (문서가 '주장'하는 값일 뿐).
- 사용자가 PATCH로 확인·수정하면 confirmed=True, 값이 바뀌었으면 source="user".
- 체류 법령은 지금 시행 중인 법령으로 판단하므로 효력 기준일은 오늘(한국 날짜)이다.
"""

import re
from datetime import date

FACT_KEYS = ("doc_type", "residence_status", "expiry_date", "deadline", "amount", "parties", "issuer", "other")
DATE_KEYS = ("expiry_date", "deadline")

_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DMY = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b")
_VI = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I)
# 2026. 11. 9. / 2026년 11월 9일
_KO = re.compile(r"(\d{4})\s*[.년]\s*(\d{1,2})\s*[.월]\s*(\d{1,2})")


class FactError(ValueError):
    pass


def parse_date(value: str | None) -> date | None:
    """ISO(YYYY-MM-DD), DD/MM/YYYY(베트남식 일/월 순서), 'ngày 2 tháng 9 năm 2026'을 읽는다."""
    if not value:
        return None
    s = value.strip()
    for pattern, order in ((_ISO, "ymd"), (_KO, "ymd"), (_DMY, "dmy"), (_VI, "dmy")):
        m = pattern.search(s)
        if not m:
            continue
        a, b, c = (int(x) for x in m.groups())
        y, mo, d = (a, b, c) if order == "ymd" else (c, b, a)
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    return None


def _norm(v: str | None) -> str:
    return " ".join((v or "").split()).casefold()


def _clean_value(key: str, value: str) -> str:
    value = value.strip()
    if key in DATE_KEYS and value and parse_date(value) is not None:
        return parse_date(value).isoformat()
    if key == "incident_date" and value:
        d = parse_date(value)
        if d is None:
            raise FactError("Enter the incident date as YYYY-MM-DD or DD/MM/YYYY.")
        return d.isoformat()
    return value


def initial_facts(doc_facts: list[dict]) -> list[dict]:
    """인테이크 결과 → 저장용 사실 목록. 사건일은 ISO로 맞추고, 읽을 수 없으면 사건일로 쓰지 않는다."""
    out = []
    for i, f in enumerate(doc_facts):
        key, value = f.get("key"), (f.get("value") or "").strip()
        if key not in FACT_KEYS or not value:
            continue
        if key == "incident_date":
            d = parse_date(value)
            if d is None:
                key = "other"
            else:
                value = d.isoformat()
        out.append({"id": f"f{i + 1}", "key": key, "label": f.get("label") or key, "value": value,
                    "source": "document", "confirmed": False})
    return out


def _match(current: list[dict], sub: dict, taken: set[int]) -> int | None:
    """제출된 사실이 기존 어느 사실을 가리키는지: id → (key, label) → 같은 key가 하나뿐일 때 key."""
    free = [i for i in range(len(current)) if i not in taken]
    if sub.get("id"):
        hit = [i for i in free if current[i]["id"] == sub["id"]]
        if hit:
            return hit[0]
    hit = [i for i in free if current[i]["key"] == sub["key"] and _norm(current[i]["label"]) == _norm(sub.get("label"))]
    if hit:
        return hit[0]
    same_key = [i for i, f in enumerate(current) if f["key"] == sub["key"]]
    if len(same_key) == 1 and same_key[0] in free:
        return same_key[0]
    return None


def merge_facts(current: list[dict], submitted: list[dict], document: list[dict]) -> list[dict]:
    """PATCH 병합. 제출된 사실은 모두 confirmed=True가 된다.

    - 문서가 적은 값과 같으면 source="document", 다르면 "user".
    - 값이 빈 문자열이면 그 사실을 지운다.
    - 제출되지 않은 기존 사실은 그대로 둔다.
    """
    doc_value = {f["id"]: f["value"] for f in document}
    out = [dict(f) for f in current]
    removed: set[int] = set()
    taken: set[int] = set()
    next_no = max((int(f["id"][1:]) for f in current if re.fullmatch(r"f\d+", f.get("id", ""))), default=0) + 1
    for sub in submitted:
        key = sub.get("key")
        if key not in FACT_KEYS:
            raise FactError(f"Unknown fact key: {key}")
        value = _clean_value(key, sub.get("value") or "")
        i = _match(out, sub, taken)
        if i is None:
            if value:
                out.append({"id": f"f{next_no}", "key": key, "label": (sub.get("label") or key).strip(),
                            "value": value, "source": "user", "confirmed": True})
                taken.add(len(out) - 1)
                next_no += 1
            continue
        taken.add(i)
        if not value:
            removed.add(i)
            continue
        f = out[i]
        original = doc_value.get(f["id"])
        f.update(label=(sub.get("label") or f["label"]).strip(), value=value, confirmed=True,
                 source="document" if original is not None and _norm(original) == _norm(value) else "user")
    return [f for i, f in enumerate(out) if i not in removed]


def public(facts: list[dict]) -> list[dict]:
    return [{k: f[k] for k in ("id", "key", "label", "value", "source", "confirmed")} for f in facts]
