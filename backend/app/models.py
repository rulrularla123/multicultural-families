from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, LONGTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CaseStatus(StrEnum):
    PREPARING = "준비중"
    CHECKING = "자동 점검중"
    REVIEWING = "담당자 승인 대기"
    COLLECTING = "서류 준비중"
    REQUESTED = "준비 확인 요청"
    SUPPLEMENT = "보완 요청"
    COMPLETED = "준비 확인 완료"
    CANCELED = "취소 완료"


class Base(DeclarativeBase):
    pass


class PreparationCase(Base):
    __tablename__ = "preparation_cases"
    __table_args__ = (
        CheckConstraint(
            "status IN (" + ",".join(repr(s.value) for s in CaseStatus) + ")",
            name="ck_case_status",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    display_language: Mapped[str] = mapped_column(String(32), nullable=False)
    support_type: Mapped[str] = mapped_column(String(16), default="F-6-1", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=CaseStatus.PREPARING.value, nullable=False)
    situation_version: Mapped[int] = mapped_column(default=1, nullable=False)
    document_version: Mapped[int] = mapped_column(default=1, nullable=False)
    current_check_task_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now, nullable=False)


class CheckResult(Base):
    __tablename__ = "check_results"
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("preparation_cases.id"), nullable=False, index=True)
    situation_version: Mapped[int] = mapped_column(nullable=False)
    document_version: Mapped[int] = mapped_column(nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(64))
    analysis_items: Mapped[list] = mapped_column(JSON, nullable=False)
    criterion_versions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    invalidated_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))


class CaseHistory(Base):
    __tablename__ = "case_histories"
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("preparation_cases.id"), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    criterion_versions: Mapped[list] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now, nullable=False)
