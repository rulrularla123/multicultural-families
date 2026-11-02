import os

from sqlalchemy import create_engine
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
