from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, LONGBLOB, LONGTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


MAX_SITUATION_LENGTH = 1000
MAX_FILES = 5
MAX_FILE_BYTES = 10_485_760
PDF_SIGNATURE = b"%PDF-"

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
    display_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    support_type: Mapped[str] = mapped_column(String(16), default="F-6-1", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=CaseStatus.PREPARING.value, nullable=False)
    situation_version: Mapped[int] = mapped_column(default=1, nullable=False)
    document_version: Mapped[int] = mapped_column(default=1, nullable=False)
    current_check_task_id: Mapped[str | None] = mapped_column(String(64))
    office: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now, nullable=False)


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(f"size_bytes >= 0 AND size_bytes <= {MAX_FILE_BYTES}", name="ck_attachment_size"),
        CheckConstraint("document_version >= 1", name="ck_attachment_document_version"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("preparation_cases.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    document_version: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=1, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    file_data: Mapped[bytes | None] = mapped_column(LONGBLOB, nullable=True, deferred=True)


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
    reviewed_items: Mapped[list | None] = mapped_column(JSON)
    review_reason: Mapped[str | None] = mapped_column(Text)
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
    action: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    criterion_versions: Mapped[list] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now, nullable=False)


class Criterion(Base):
    """F-02 등록 담당자가 사용한다. office=NULL은 공통 기준이다."""
    __tablename__ = "criteria"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_criterion_version"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    support_type: Mapped[str] = mapped_column(String(16), nullable=False, default="F-6-1", index=True)
    office: Mapped[str | None] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    checked_on: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=1, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CaseApproval(Base):
    """초안과 분리한 불변 공개 스냅샷. 새 점검 뒤 재사용하지 않는다."""
    __tablename__ = "case_approvals"
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("preparation_cases.id"), nullable=False, index=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("check_results.id"), nullable=False)
    situation_version: Mapped[int] = mapped_column(nullable=False)
    document_version: Mapped[int] = mapped_column(nullable=False)
    criterion_versions: Mapped[list] = mapped_column(JSON, nullable=False)
    items: Mapped[list] = mapped_column(JSON, nullable=False)
    display_language: Mapped[str | None] = mapped_column(String(32))
    approved_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now, nullable=False)
    invalidated_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))


class PreparationItem(Base):
    __tablename__ = "preparation_items"
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("preparation_cases.id"), nullable=False, index=True)
    approval_id: Mapped[int] = mapped_column(ForeignKey("case_approvals.id"), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str | None] = mapped_column(Text)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("criteria.id"), nullable=False)
    prepared: Mapped[bool | None] = mapped_column(Boolean)
    needs_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supplement_reason: Mapped[str | None] = mapped_column(Text)
    supplement_resolved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
