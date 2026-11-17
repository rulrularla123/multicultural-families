"""법령 판(버전) 관리: 적재한 판 정보, 최신 판 판정, 공식 링크, 경고 기준.

US-07(현행 여부 계산·적재), US-02(근거 조문 원문 확인), US-01(근거 없는 단정 금지·상담 안내)
"""

from datetime import UTC, date, datetime, timedelta

import httpx

from app.core.law_version import version_warning
from ingest.loader import load_file
from ingest.sources.versions import (
    Version,
    article_url,
    check_legalize_kr,
    judge,
    parse_law_search,
    version_url,
)

TODAY = date(2026, 11, 17)


def _md(mst: str, effective: str) -> str:
    return f"---\n제목: 출입국관리법\n법령MST: {mst}\n시행일자: {effective}\n상태: 시행\n---\n\n# 출입국관리법\n"


def test_loader_reads_version_fields_from_front_matter(laws_dir):
    """US-07: 머리말의 법령MST·법령ID·공포번호를 판 정보로 읽는다."""
    m = load_file(laws_dir / "출입국관리법" / "법률.md").meta
    assert m["law_mst"] and m["law_mst"].isdigit()
    assert m["law_id"] and m["promulgation_no"]


def test_judge_current_when_in_force_matches_loaded():
    r = judge("출입국관리법", "100", Version("100", date(2026, 10, 2)), Version("100", date(2026, 10, 2)), "x", TODAY)
    assert r.status == "current" and r.upcoming_mst is None


def test_judge_upcoming_when_newer_version_not_yet_in_force():
    newest = Version("200", date(2027, 1, 1))
    r = judge("출입국관리법", "100", Version("100", date(2026, 10, 2)), newest, "x", TODAY)
    assert r.status == "upcoming"
    assert r.upcoming_mst == "200" and r.upcoming_effective_from == date(2027, 1, 1)


def test_judge_outdated_when_newer_version_already_in_force():
    r = judge("출입국관리법", "100", Version("150", date(2026, 11, 1)), Version("150", date(2026, 11, 1)), "x", TODAY)
    assert r.status == "outdated" and r.latest_mst == "150"


def test_judge_unknown_without_loaded_mst_or_comparison():
    assert judge("a", None, Version("1", TODAY), None, "x", TODAY).status == "unknown"
    assert judge("a", "1", None, None, "x", TODAY).status == "unknown"


def test_legalize_kr_check_walks_history_when_latest_is_future():
    """최신 판이 시행 전이면 이력에서 오늘 시행 중인 판을 찾아 적재한 판과 비교한다."""
    def handler(req: httpx.Request) -> httpx.Response:
        if "api.github.com" in req.url.host:
            return httpx.Response(200, json=[{"sha": "new"}, {"sha": "old"}])
        if "/main/" in req.url.path:
            return httpx.Response(200, text=_md("200", "2027-01-01"))
        return httpx.Response(200, text=_md("100", "2026-10-02"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        r = check_legalize_kr(client, "출입국관리법", "법률", "출입국관리법", "100", TODAY)
    assert r.status == "upcoming" and r.latest_mst == "100" and r.upcoming_mst == "200"
    assert r.source == "legalize-kr"


def test_legalize_kr_check_network_error_is_unknown():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        r = check_legalize_kr(client, "출입국관리법", "법률", "출입국관리법", "100", TODAY)
    assert r.status == "unknown" and "실패" in r.reason


def test_parse_law_search_matches_exact_title_only():
    data = {"LawSearch": {"law": [
        {"법령명한글": "출입국관리법 시행령", "법령일련번호": "9", "시행일자": "20261002", "현행연혁코드": "현행"},
        {"법령명한글": "출입국관리법", "법령일련번호": "290729", "시행일자": "20261002", "현행연혁코드": "현행"},
    ]}}
    v = parse_law_search(data, "출입국관리법")
    assert v == Version("290729", date(2026, 10, 2))
    assert parse_law_search(data, "국적법") is None


def test_official_links():
    """US-02: 적재한 판의 원문과 지금 시행 중인 판의 조문으로 가는 국가법령정보센터 링크."""
    assert version_url("290729") == "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=290729"
    assert version_url(None) is None
    assert article_url("출입국관리법", "10의2") == "https://www.law.go.kr/법령/출입국관리법/제10조의2"
    assert article_url("출입국관리법 시행령", "12") == "https://www.law.go.kr/법령/출입국관리법시행령/제12조"
    assert article_url("국적법", None) == "https://www.law.go.kr/법령/국적법"


def test_version_warning_rules():
    now = datetime(2026, 11, 17, tzinfo=UTC)
    assert version_warning("outdated", now, now) == "outdated"
    assert version_warning("current", now - timedelta(days=1), now) is None
    assert version_warning("upcoming", now - timedelta(days=1), now) is None
    assert version_warning("current", now - timedelta(days=30), now) == "unchecked"
    assert version_warning("unknown", now, now) == "unchecked"
    assert version_warning("current", None, now) == "unchecked"
