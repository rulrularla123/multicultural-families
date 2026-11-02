import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url

from app.database import build_engine, session_factory
from app.main import create_app
from app.models import Base, CaseHistory, CheckResult, PreparationCase
from app.seed import seed_demo


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL에 이름이 _test로 끝나는 전용 MySQL 테스트 DB를 지정하세요.")
    engine = build_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def factory(engine):
    factory = session_factory(engine)
    with factory.begin() as session:
        for model in (CaseHistory, CheckResult, PreparationCase):
            session.execute(delete(model))
        seed_demo(session, "test-language")
    return factory


@pytest.fixture
def client(engine, factory):
    with TestClient(create_app(engine=engine, demo_mode=True)) as client:
        yield client
