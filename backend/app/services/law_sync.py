"""법령 최신 판 자동 동기화.

서버가 켜져 있는 동안 주기적으로 `ingest sync`와 같은 일을 한다. 공식 사이트와 DB의 판을 비교해, 새 판이
시행 중인 법령만 다시 받아 적재하고 그 법령의 요약·임베딩을 새로 만든다.

- 주기: `LAW_SYNC_INTERVAL_HOURS`(기본 24). 0이면 끈다.
- 마지막 확인(`legal_documents.version_checked_at`)이 주기보다 오래됐을 때만 돈다. 서버를 다시 켜도 바로 다시
  돌지 않는다.
- 서버 프로세스가 여러 개여도 PostgreSQL advisory lock으로 한 곳에서만 돈다.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionLocal, engine

log = logging.getLogger(__name__)

LAWS_DIR = Path(__file__).resolve().parents[2] / "data" / "laws"
LOCK_KEY = 72_6001  # advisory lock 번호 (이 기능 전용)
POLL_SECONDS = 600  # 동기화할 때가 됐는지 보는 간격
RETRY_AFTER = timedelta(hours=1)  # 실패한 뒤 다시 시도할 때까지


@dataclass
class SyncState:
    """마지막 자동 동기화 결과. /health에 보여 준다."""

    last_run_at: datetime | None = None
    changed: list[str] = field(default_factory=list)
    reloaded: list[str] = field(default_factory=list)
    still_outdated: list[str] = field(default_factory=list)
    embedded: int = 0
    reindexed: list[str] = field(default_factory=list)
    pending_reindex: list[str] = field(default_factory=list)
    llm_skipped: bool = False
    error: str | None = None

    def as_dict(self) -> dict:
        s = get_settings()
        return {
            "enabled": s.law_sync_interval_hours > 0,
            "interval_hours": s.law_sync_interval_hours,
            "last_run_at": self.last_run_at,
            "changed": self.changed,
            "reloaded": self.reloaded,
            "still_outdated": self.still_outdated,
            "embedded": self.embedded,
            "reindexed": self.reindexed,
            "pending_reindex": self.pending_reindex,
            "llm_skipped": self.llm_skipped,
            "error": self.error,
        }


state = SyncState()


def is_due(last_checked: datetime | None, now: datetime, interval_hours: float) -> bool:
    """한 번도 확인하지 않았거나, 가장 오래된 확인이 주기보다 오래됐으면 동기화한다."""
    if interval_hours <= 0:
        return False
    return last_checked is None or now - last_checked >= timedelta(hours=interval_hours)


async def run_if_due(now: datetime | None = None) -> bool:
    """때가 됐으면 한 번 동기화한다. 실제로 돌았으면 True."""
    from app.core.lang import today_kr
    from ingest import pipeline

    settings = get_settings()
    now = now or datetime.now(UTC)
    async with SessionLocal() as session:
        last, has_docs, pending = (await session.execute(text(
            "SELECT CASE WHEN count(version_checked_at) = count(*) THEN min(version_checked_at) END, "
            "count(*), count(*) FILTER (WHERE needs_reindex) "
            "FROM legal_documents WHERE NOT is_sample"
        ))).one()
    if not has_docs or settings.law_sync_interval_hours <= 0:
        return False
    # 실패 직후에는 한 시간 쉬고 다시 시도한다
    if state.error and state.last_run_at and now - state.last_run_at < RETRY_AFTER:
        return False
    # 요약·임베딩을 기다리는 법령이 있고 실제 LLM이 켜져 있으면 주기와 관계없이 채운다
    waiting = pending > 0 and not settings.llm_fake
    if not waiting and not is_due(last, now, settings.law_sync_interval_hours):
        return False

    # 작업 세션은 커밋할 때마다 연결을 돌려주므로, 잠금은 따로 잡아 둔 연결에서 걸고 푼다
    async with engine.connect() as lock_conn:
        got = (await lock_conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})).scalar_one()
        if not got:
            log.info("법령 동기화: 다른 서버 프로세스가 진행 중이라 건너뜁니다")
            return False
        try:
            log.info("법령 동기화 시작 (마지막 확인 %s)", last)
            async with SessionLocal() as session:
                report = await pipeline.sync_versions(session, LAWS_DIR, today_kr())
            state.last_run_at = now
            state.changed = report["changed"]
            state.reloaded = report["reloaded"]
            state.still_outdated = report["still_outdated"]
            state.embedded = report["embedded"]
            state.reindexed = report["reindexed"]
            state.pending_reindex = report["pending_reindex"]
            state.llm_skipped = report["llm_skipped"]
            state.error = None
            log.info("법령 동기화 끝: 새 판 %s, 재적재 %s, 임베딩 %d개, 아직 옛 판 %s",
                     report["changed"], report["reloaded"], report["embedded"], report["still_outdated"])
        except Exception as e:  # 다음 주기에 다시 시도한다. 서버는 계속 돈다
            state.last_run_at = now
            state.error = f"{type(e).__name__}: {e}"
            log.exception("법령 동기화 실패")
        finally:
            await lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
            await lock_conn.commit()
        return True


async def sync_loop(poll_seconds: int = POLL_SECONDS) -> None:
    """서버가 켜져 있는 동안 poll_seconds마다 동기화할 때가 됐는지 본다."""
    while True:
        try:
            await run_if_due()
        except Exception:
            log.exception("법령 동기화 확인 실패")
        await asyncio.sleep(poll_seconds)
