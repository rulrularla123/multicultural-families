"""legalize-kr 저장소(https://github.com/legalize-kr/legalize-kr)에서 법령 마크다운을 받는다.

법제처 국가법령정보센터의 법령을 조문 구조 그대로 마크다운으로 관리하는 공개 저장소다.
파일 머리말에 시행일자·상태·법제처 출처가 들어 있다.
"""

import logging
import re
from datetime import date
from pathlib import Path

import httpx

from app.core.lang import today_kr

log = logging.getLogger("ingest")
RAW = "https://raw.githubusercontent.com/legalize-kr/legalize-kr/{ref}/kr/{family}/{kind}.md"
COMMITS = "https://api.github.com/repos/legalize-kr/legalize-kr/commits"
_EFFECTIVE = re.compile(r"^시행일자:\s*'?(\d{4}-\d{2}-\d{2})", re.M)

# 다문화가족 체류(F-6)에 필요한 법령. 폴더 이름은 legalize-kr과 같다 (법령명에서 띄어쓰기 제거)
DEFAULT_LAWS = ["출입국관리법", "재한외국인처우기본법", "다문화가족지원법", "국적법"]
KINDS = ["법률", "시행령", "시행규칙"]


def _effective(text: str) -> date | None:
    m = _EFFECTIVE.search(text)
    return date.fromisoformat(m.group(1)) if m else None


def _in_force_version(client: httpx.Client, family: str, kind: str, latest: str, today: date) -> str:
    """최신 판이 아직 시행 전이면, 개정 이력(커밋)을 거슬러 오늘 시행 중인 판을 찾는다."""
    eff = _effective(latest)
    if eff is None or eff <= today:
        return latest
    r = client.get(COMMITS, params={"path": f"kr/{family}/{kind}.md", "per_page": 30})
    r.raise_for_status()
    for c in r.json()[1:]:
        text = client.get(RAW.format(ref=c["sha"], family=family, kind=kind)).text
        old = _effective(text)
        if old and old <= today:
            log.info("%s/%s: 최신 판은 %s 시행 예정 → %s 시행 판을 씁니다", family, kind, eff, old)
            return text
    log.warning("%s/%s: 오늘 시행 중인 이전 판을 찾지 못해 최신 판(%s 시행)을 씁니다", family, kind, eff)
    return latest


def fetch(families: list[str], out: Path, today: date | None = None) -> list[Path]:
    today = today or today_kr()
    written: list[Path] = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for family in families:
            for kind in KINDS:
                r = client.get(RAW.format(ref="main", family=family, kind=kind))
                if r.status_code == 404:
                    continue  # 시행규칙이 없는 법령도 있다
                r.raise_for_status()
                text = _in_force_version(client, family, kind, r.text, today)
                path = out / family / f"{kind}.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                written.append(path)
                log.info("받음: %s (%d자)", path, len(text))
    return written
