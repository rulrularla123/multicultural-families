"""data/laws/{법령}/{법률|시행령|시행규칙}.md (legalize-kr 형식) 법령 원본을 읽는다.

파일 머리말(--- … ---)의 제목·법령구분·시행일자·상태·출처를 메타데이터로 쓴다.
폴더 이름이 '_'로 시작하면 샘플(테스트) 데이터로 취급한다.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.lang import today_kr
from ingest.nlp.normalize import normalize_text

KINDS = {"법률": "law", "시행령": "decree", "시행규칙": "rule"}
_FRONT = re.compile(r"^---\n(.*?)\n---\n", re.S)


@dataclass
class RawDocument:
    path: Path
    meta: dict
    text: str
    raw_hash: str

    @property
    def id(self) -> str:
        return self.meta["id"]

    def date(self, key: str) -> date | None:
        v = self.meta.get(key)
        return date.fromisoformat(v) if v else None


def parse_front_matter(raw: str) -> tuple[dict, str]:
    """머리말의 단순한 YAML(키: 값, '- 항목' 목록)만 읽는다."""
    m = _FRONT.match(raw)
    if not m:
        raise ValueError("머리말(--- … ---)이 없습니다")
    meta: dict = {}
    key = None
    for line in m.group(1).split("\n"):
        if line.startswith("- ") and key:
            meta.setdefault(key, [])
            if isinstance(meta[key], list):
                meta[key].append(line[2:].strip().strip("'\""))
            continue
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            key, value = key.strip(), value.strip().strip("'\"")
            meta[key] = value if value else []
    return meta, raw[m.end():]


def doc_id(family: str, kind: str) -> str:
    return family if kind == "법률" else f"{family}{kind}"


def load_file(path: Path) -> RawDocument:
    family, kind = path.parent.name.lstrip("_"), path.stem
    if kind not in KINDS:
        raise ValueError(f"{path}: 파일 이름은 법률·시행령·시행규칙 중 하나여야 합니다")
    raw = path.read_text(encoding="utf-8")
    front, body = parse_front_matter(raw)
    if not front.get("제목"):
        raise ValueError(f"{path}: 머리말에 제목이 없습니다")
    effective = front.get("시행일자") or None
    status = "repealed" if "폐지" in str(front.get("상태", "")) else "in_force"
    if status == "in_force" and effective and date.fromisoformat(effective) > today_kr():
        status = "not_yet"
    issuer = front.get("소관부처")
    family_dir = path.parent
    guides = []
    if kind != "법률" and (family_dir / "법률.md").exists():
        guides.append(doc_id(family, "법률"))
    if kind == "시행규칙" and (family_dir / "시행령.md").exists():
        guides.append(doc_id(family, "시행령"))
    meta = {
        "id": doc_id(family, kind),
        "doc_type": KINDS[kind],
        "title_ko": front["제목"],
        "short_names": [front["제목"].replace(" ", "")],
        "issuer": ", ".join(issuer) if isinstance(issuer, list) else (issuer or None),
        "issued_date": front.get("공포일자") or None,
        "effective_from": effective,
        "status": status,
        "source_url": front.get("출처") or None,
        "guides": guides,
        "is_sample": path.parent.name.startswith("_"),
    }
    return RawDocument(path, meta, normalize_text(body), hashlib.sha256(raw.encode()).hexdigest())


def discover(root: Path, include_samples: bool = False) -> list[RawDocument]:
    docs = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        if folder.name.startswith("_") and not include_samples:
            continue
        for kind in KINDS:
            path = folder / f"{kind}.md"
            if path.exists():
                docs.append(load_file(path))
    return docs
