"""적재한 법령 판이 최신인지에 따른 경고. 조문 화면과 답변이 같은 기준을 쓴다."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from app.core.config import get_settings

VersionWarning = Literal["outdated", "unchecked"]


def version_warning(status: str | None, checked_at: datetime | None,
                    now: datetime | None = None) -> VersionWarning | None:
    """outdated: 더 새로운 판이 시행 중이다. unchecked: 확인하지 못했거나 확인한 지 오래됐다."""
    if status == "outdated":
        return "outdated"
    now = now or datetime.now(UTC)
    max_age = timedelta(days=get_settings().law_version_max_age_days)
    if status not in ("current", "upcoming") or checked_at is None or now - checked_at > max_age:
        return "unchecked"
    return None
