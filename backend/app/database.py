import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL에 전용 MySQL 데이터베이스를 지정하세요.")
    parsed = make_url(url)
    if parsed.drivername != "mysql+pymysql":
        raise RuntimeError("이 서버는 mysql+pymysql 연결을 사용합니다.")
    return create_engine(parsed, pool_pre_ping=True, connect_args={"charset": "utf8mb4"})


def session_factory(engine: Engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def prepare_us01_schema(engine: Engine) -> list[str]:
    """기존 데이터를 유지하며 US-01에 필요한 추가·nullable 변경만 적용한다."""
    from .models import Base

    Base.metadata.create_all(engine)
    changes = []
    case_columns = {column["name"]: column for column in inspect(engine).get_columns("preparation_cases")}
    if not case_columns["display_language"]["nullable"]:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE preparation_cases MODIFY COLUMN display_language VARCHAR(32) NULL"))
        changes.append("display_language NULL 허용 적용")
    attachment_columns = {column["name"] for column in inspect(engine).get_columns("attachments")}
    if "file_data" not in attachment_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE attachments ADD COLUMN file_data LONGBLOB NULL"))
        changes.append("attachments.file_data 추가")
    return changes


if __name__ == "__main__":
    if os.environ.get("DEMO_MODE") != "1":
        raise SystemExit("전용 모의 DB에 명시적으로 적용합니다. DEMO_MODE=1로 실행하세요.")
    engine = build_engine()
    try:
        changes = prepare_us01_schema(engine)
        print("US-01 스키마 준비 완료. " + (" / ".join(changes) if changes else "추가 변경 없음."))
    finally:
        engine.dispose()
