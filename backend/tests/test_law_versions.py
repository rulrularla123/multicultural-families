"""법령 판(버전) 관리: 적재한 판 정보, 최신 판 판정, 공식 링크, 경고 기준.

US-07(현행 여부 계산·적재), US-02(근거 조문 원문 확인), US-01(근거 없는 단정 금지·상담 안내)
"""

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

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


# ---------------------------------------------------------------------------
# 동기화: 바뀐 법령만 다시 받아 요약·임베딩 (DB 필요)
# ---------------------------------------------------------------------------

LAW_V2 = """---
제목: 버전시험법
법령MST: '200'
법령ID: '999'
법령구분: 법률
공포일자: 2026-11-01
공포번호: '2'
시행일자: 2026-11-10
상태: 시행
출처: https://www.law.go.kr/법령/버전시험법
---

# 버전시험법

##### 제1조 (목적)
이 법은 판 동기화를 시험한다. <개정 2026.11.1>

##### 제2조 (기간)
신고는 30일 이내에 한다.
"""


@pytest.mark.db
def test_sync_reloads_only_changed_law_and_reembeds(tmp_path, monkeypatch):
    """US-07: 새 판이 시행 중인 법령만 다시 적재하고, 그 법령의 요약·임베딩만 새로 만든다."""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import get_settings
    from ingest import pipeline
    from ingest.loader import discover
    from ingest.sources import legalize_kr
    from ingest.sources.versions import VersionCheck

    doc_id = "버전시험법"
    root = tmp_path / "laws"
    (root / doc_id).mkdir(parents=True)
    (root / doc_id / "법률.md").write_text(LAW_V2.replace("'200'", "'100'").replace("30일", "14일"), encoding="utf-8")

    other_before: dict = {}
    calls = {"fetch": [], "summaries": 0, "embedded": 0}

    def fake_fetch(families, out, today=None):
        calls["fetch"].append(list(families))
        (out / doc_id / "법률.md").write_text(LAW_V2, encoding="utf-8")
        return []

    async def fake_check(session, today):
        mst = (await session.execute(text("SELECT law_mst FROM legal_documents WHERE id = :i"), {"i": doc_id}))
        status = "current" if mst.scalar_one() == "200" else "outdated"
        return [VersionCheck(doc_id, status, "legalize-kr", latest_mst="200")]

    async def fake_complete(instructions, prompt):
        calls["summaries"] += 1
        return "요약"

    async def fake_embed(texts):
        calls["embedded"] += len(texts)
        return [[0.0] * 1536 for _ in texts]

    monkeypatch.setattr(legalize_kr, "fetch", fake_fetch)
    monkeypatch.setattr(pipeline, "check_versions", fake_check)
    monkeypatch.setattr(pipeline, "complete", fake_complete)
    monkeypatch.setattr(pipeline, "embed_texts", fake_embed)
    monkeypatch.setattr(get_settings(), "llm_fake", True)

    async def run():
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with Session() as s:
                await pipeline.load_documents(s, discover(root))
                # 옛 판: 요약(vi)과 임베딩이 있는 상태
                await s.execute(text(
                    "INSERT INTO chunks (provision_id, jo_id, document_id, kind, lang, content, domains) "
                    "SELECT id, id, document_id, 'summary', 'vi', 'old', '{}' FROM provisions "
                    "WHERE document_id = :d AND level = 'jo'"), {"d": doc_id})
                await s.execute(text("UPDATE chunks SET embedding = array_fill(0.5::float4, ARRAY[1536])::vector "
                                     "WHERE document_id = :d"), {"d": doc_id})
                # 요약 언어는 다른 법령에 있는 언어를 따른다: 다른 법령에 vi 요약 표식 하나를 둔다
                await s.execute(text(
                    "INSERT INTO chunks (provision_id, jo_id, document_id, kind, lang, content, domains) "
                    "SELECT id, id, document_id, 'summary', 'vi', 'sync-test-marker', '{}' FROM provisions "
                    "WHERE document_id <> :d AND level = 'jo' LIMIT 1"), {"d": doc_id})
                await s.commit()
                other_before.update(dict((await s.execute(text(
                    "SELECT document_id, count(embedding) FROM chunks WHERE document_id <> :d GROUP BY 1"
                ), {"d": doc_id})).all()))

                # 1차: LLM_FAKE라 재적재만 하고 요약·임베딩은 대기로 남긴다
                first = await pipeline.sync_versions(s, root, TODAY)
                waiting = (await s.execute(text(
                    "SELECT needs_reindex FROM legal_documents WHERE id = :d"), {"d": doc_id})).scalar_one()
                # 2차: 실제 LLM이 켜지면 판이 같아도 대기 중인 법령의 요약·임베딩을 채운다
                monkeypatch.setattr(get_settings(), "llm_fake", False)
                report = await pipeline.sync_versions(s, root, TODAY)
                report["first"] = first
                report["waiting"] = waiting
                report["after_flag"] = (await s.execute(text(
                    "SELECT needs_reindex FROM legal_documents WHERE id = :d"), {"d": doc_id})).scalar_one()

                text_ = (await s.execute(text(
                    "SELECT full_text_ko FROM provisions WHERE id = :i"), {"i": f"{doc_id}:J2"})).scalar_one()
                emb = (await s.execute(text(
                    "SELECT count(*), count(embedding) FROM chunks WHERE document_id = :d"), {"d": doc_id})).one()
                summaries = (await s.execute(text(
                    "SELECT content FROM chunks WHERE document_id = :d AND kind = 'summary'"), {"d": doc_id}
                )).scalars().all()
                other_after = dict((await s.execute(text(
                    "SELECT document_id, count(embedding) FROM chunks WHERE document_id <> :d GROUP BY 1"
                ), {"d": doc_id})).all())
                return report, text_, emb, summaries, other_after
        finally:
            async with Session() as s:
                await s.execute(text("DELETE FROM legal_documents WHERE id = :d"), {"d": doc_id})
                await s.execute(text("DELETE FROM chunks WHERE content = 'sync-test-marker'"))
                await s.commit()
                await pipeline.rebuild_relations(s)
            await engine.dispose()

    report, text_, emb, summaries, other_after = asyncio.run(run())
    first = report["first"]
    assert calls["fetch"] == [[doc_id]]                      # 받기는 1차에서 한 번만
    assert first["changed"] == [doc_id] and first["reloaded"] == [doc_id]
    assert first["llm_skipped"] and first["pending_reindex"] == [doc_id] and report["waiting"] is True
    assert first["still_outdated"] == []
    assert report["changed"] == [] and report["reindexed"] == [doc_id] and report["after_flag"] is False
    assert "30일" in text_                                  # 새 판 원문으로 바뀜
    assert emb[0] == emb[1] and calls["embedded"] == emb[0]  # 이 법령 청크만 모두 새로 임베딩
    assert summaries and all(s.endswith("요약") for s in summaries)
    assert other_after == other_before                      # 다른 법령은 건드리지 않음


def test_sync_due_rules():
    """자동 동기화: 확인한 적 없거나 주기가 지났을 때만, 주기 0이면 끔."""
    from app.services.law_sync import is_due

    now = datetime(2026, 11, 17, tzinfo=UTC)
    assert is_due(None, now, 24)
    assert is_due(now - timedelta(hours=25), now, 24)
    assert not is_due(now - timedelta(hours=1), now, 24)
    assert not is_due(None, now, 0)


def test_server_does_not_start_sync_when_disabled():
    """테스트 설정(LAW_SYNC_INTERVAL_HOURS=0)에서는 서버가 자동 동기화를 돌리지 않는다."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import law_sync

    called = []
    orig = law_sync.sync_loop
    law_sync.sync_loop = lambda *a, **k: called.append(1)
    try:
        with TestClient(app):
            pass
    finally:
        law_sync.sync_loop = orig
    assert called == []
