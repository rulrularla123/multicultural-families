"""적재한 법령 판(법령MST)이 지금 시행 중인 최신 판인지 확인한다.

확인 순서
1. `LAW_GO_KR_OC`가 있으면 국가법령정보센터 Open API(법제처 공식)의 현행 법령 목록과 비교한다.
2. 없으면(또는 실패하면) legalize-kr 저장소의 최신 판과 비교한다. legalize-kr은 법제처 법령을 옮긴 저장소라
   공식 사이트보다 늦을 수 있으므로, 결과에 어디와 비교했는지(`checked_source`)를 남긴다.

판정
- current: 지금 시행 중인 판이 적재한 판과 같다
- upcoming: 적재한 판이 현행이지만, 공포되어 시행을 기다리는 개정판이 있다
- outdated: 적재한 판보다 새로운 판이 이미 시행 중이다 → 다시 받아 적재해야 한다
- unknown: 확인하지 못했다(네트워크 오류, 목록에 없음 등)
"""

import logging
from dataclasses import dataclass
from datetime import date

import httpx

from app.core.config import get_settings
from ingest.loader import parse_front_matter
from ingest.sources.legalize_kr import COMMITS, RAW

log = logging.getLogger("ingest")

LAW_SEARCH = "https://www.law.go.kr/DRF/lawSearch.do"
KIND_BY_TYPE = {"law": "법률", "decree": "시행령", "rule": "시행규칙"}


def version_url(mst: str | None) -> str | None:
    """적재한 바로 그 판의 국가법령정보센터 원문 주소 (법령일련번호 = 법령MST)."""
    return f"https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq={mst}" if mst else None


def article_url(title_ko: str, jo_number: str | None) -> str:
    """국가법령정보센터에서 지금 시행 중인 판의 해당 조를 여는 주소. jo_number는 '25', '10의2' 형식."""
    base = f"https://www.law.go.kr/법령/{title_ko.replace(' ', '')}"  # legalize-kr 머리말 '출처'와 같은 형식
    if not jo_number:
        return base
    main, _, branch = jo_number.partition("의")
    return f"{base}/제{main}조" + (f"의{branch}" if branch else "")


def family_of(document_id: str, doc_type: str) -> tuple[str, str] | None:
    """문서 ID → (legalize-kr 법령 폴더, 법률|시행령|시행규칙). '출입국관리법시행령' → ('출입국관리법', '시행령')"""
    kind = KIND_BY_TYPE.get(doc_type)
    if kind is None:
        return None
    return (document_id if kind == "법률" else document_id.removesuffix(kind)), kind


@dataclass
class Version:
    mst: str
    effective_from: date | None


@dataclass
class VersionCheck:
    document_id: str
    status: str                       # current | upcoming | outdated | unknown
    source: str                       # law.go.kr | legalize-kr
    latest_mst: str | None = None     # 지금 시행 중인 판
    upcoming_mst: str | None = None   # 시행 예정 판
    upcoming_effective_from: date | None = None
    reason: str | None = None


def judge(document_id: str, loaded_mst: str | None, in_force: Version | None, newest: Version | None,
          source: str, today: date) -> VersionCheck:
    """적재한 판 · 지금 시행 판 · 가장 새로 공포된 판을 비교한다."""
    if not loaded_mst:
        return VersionCheck(document_id, "unknown", source, reason="적재한 판의 법령MST가 없습니다")
    if in_force is None:
        return VersionCheck(document_id, "unknown", source, reason="비교할 현행 판을 찾지 못했습니다")
    upcoming = newest if newest and newest.mst != in_force.mst and newest.effective_from \
        and newest.effective_from > today else None
    if in_force.mst != loaded_mst:
        return VersionCheck(document_id, "outdated", source, latest_mst=in_force.mst,
                            upcoming_mst=upcoming.mst if upcoming else None,
                            upcoming_effective_from=upcoming.effective_from if upcoming else None,
                            reason=f"적재 {loaded_mst} → 현행 {in_force.mst}")
    if upcoming:
        return VersionCheck(document_id, "upcoming", source, latest_mst=in_force.mst, upcoming_mst=upcoming.mst,
                            upcoming_effective_from=upcoming.effective_from)
    return VersionCheck(document_id, "current", source, latest_mst=in_force.mst)


# ---------------------------------------------------------------------------
# legalize-kr
# ---------------------------------------------------------------------------

def _front_version(text: str) -> Version | None:
    try:
        meta, _ = parse_front_matter(text)
    except ValueError:
        return None
    mst = str(meta.get("법령MST") or "").strip()
    eff = meta.get("시행일자") or None
    return Version(mst, date.fromisoformat(eff)) if mst else None


def check_legalize_kr(client: httpx.Client, family: str, kind: str, document_id: str, loaded_mst: str | None,
                      today: date) -> VersionCheck:
    try:
        r = client.get(RAW.format(ref="main", family=family, kind=kind))
        r.raise_for_status()
        newest = _front_version(r.text)
        in_force = newest
        if newest and newest.effective_from and newest.effective_from > today:
            in_force = None
            c = client.get(COMMITS, params={"path": f"kr/{family}/{kind}.md", "per_page": 30})
            c.raise_for_status()
            for commit in c.json()[1:]:
                old = _front_version(client.get(RAW.format(ref=commit["sha"], family=family, kind=kind)).text)
                if old and old.effective_from and old.effective_from <= today:
                    in_force = old
                    break
    except httpx.HTTPError as e:
        return VersionCheck(document_id, "unknown", "legalize-kr", reason=f"legalize-kr 요청 실패: {e}")
    return judge(document_id, loaded_mst, in_force, newest, "legalize-kr", today)


# ---------------------------------------------------------------------------
# 국가법령정보센터 Open API (법제처 공식). 인증값 OC가 필요하다.
# ---------------------------------------------------------------------------

def _yyyymmdd(v) -> date | None:
    s = str(v or "").strip()
    return date(int(s[:4]), int(s[4:6]), int(s[6:8])) if len(s) == 8 and s.isdigit() else None


def parse_law_search(data: dict, title_ko: str) -> Version | None:
    """lawSearch.do JSON에서 법령명이 정확히 같은 현행 법령의 법령일련번호(MST)를 찾는다."""
    laws = (data.get("LawSearch") or {}).get("law") or []
    if isinstance(laws, dict):
        laws = [laws]
    want = title_ko.replace(" ", "")
    for law in laws:
        if str(law.get("법령명한글", "")).replace(" ", "") == want and law.get("현행연혁코드", "현행") == "현행":
            return Version(str(law.get("법령일련번호")), _yyyymmdd(law.get("시행일자")))
    return None


def check_law_go_kr(client: httpx.Client, oc: str, title_ko: str, document_id: str, loaded_mst: str | None,
                    today: date) -> VersionCheck:
    try:
        r = client.get(LAW_SEARCH, params={"OC": oc, "target": "law", "type": "JSON", "query": title_ko,
                                           "display": 20})
        r.raise_for_status()
        in_force = parse_law_search(r.json(), title_ko)
    except (httpx.HTTPError, ValueError) as e:
        return VersionCheck(document_id, "unknown", "law.go.kr", reason=f"국가법령정보센터 요청 실패: {e}")
    # 현행 목록만 보므로 시행 예정 판은 legalize-kr 확인에서 채운다
    return judge(document_id, loaded_mst, in_force, None, "law.go.kr", today)


def check_versions(docs: list, today: date) -> list[VersionCheck]:
    """docs: id·doc_type·title_ko·law_mst를 가진 행. 법령 폴더 이름은 법률 제목에서 띄어쓰기를 뺀 것."""
    oc = get_settings().law_go_kr_oc.strip()
    out: list[VersionCheck] = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for d in docs:
            fk = family_of(d.id, d.doc_type)
            if fk is None:
                continue
            family, kind = fk
            mirror = check_legalize_kr(client, family, kind, d.id, d.law_mst, today)
            if oc:
                official = check_law_go_kr(client, oc, d.title_ko, d.id, d.law_mst, today)
                if official.status != "unknown":
                    official.upcoming_mst = mirror.upcoming_mst
                    official.upcoming_effective_from = mirror.upcoming_effective_from
                    if official.status == "current" and mirror.upcoming_mst:
                        official.status = "upcoming"
                    out.append(official)
                    continue
                log.warning("%s: %s → legalize-kr로 확인합니다", d.id, official.reason)
            out.append(mirror)
    return out
