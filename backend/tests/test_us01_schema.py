"""US-01의 기존 전용 MySQL 스키마 업데이트와 데이터 보존 점검."""

from sqlalchemy import inspect, select, text

from app.database import prepare_us01_schema
from app.models import Attachment, PreparationCase


def test_us01_schema_upgrade_is_idempotent_and_preserves_data(engine, factory):
    with factory.begin() as session:
        session.add(Attachment(case_id=1003, filename="existing.pdf", size_bytes=12))
    try:
        # 전용 테스트 DB에서만 이전 단계의 컬럼 구성을 재현한다.
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE preparation_cases MODIFY COLUMN display_language VARCHAR(32) NOT NULL"))
            connection.execute(text("ALTER TABLE attachments DROP COLUMN file_data"))
        changes = prepare_us01_schema(engine)
        assert len(changes) == 2
        columns = {column["name"]: column for column in inspect(engine).get_columns("preparation_cases")}
        assert columns["display_language"]["nullable"] is True
        assert "file_data" in {column["name"] for column in inspect(engine).get_columns("attachments")}
        with factory() as session:
            assert session.get(PreparationCase, 1003).display_language == "test-language"
            attachment = session.scalar(select(Attachment))
            assert attachment.filename == "existing.pdf"
            assert attachment.file_data is None
        assert prepare_us01_schema(engine) == []
    finally:
        prepare_us01_schema(engine)
