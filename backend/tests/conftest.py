import os
from pathlib import Path

import pytest

# 테스트는 OpenAI를 부르지 않는다 (설정을 처음 읽기 전에 정해야 한다)
os.environ["LLM_FAKE"] = "true"

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def laws_dir() -> Path:
    return ROOT / "data" / "laws"


@pytest.fixture(scope="session")
def demo_dir() -> Path:
    return ROOT / "data" / "demo"


def pytest_collection_modifyitems(config, items):
    """DB가 필요한 테스트는 TEST_DB=1일 때만 돈다 (docker compose의 pgvector + 법령 적재 후)."""
    if os.environ.get("TEST_DB") == "1":
        return
    skip = pytest.mark.skip(reason="TEST_DB=1이 아니라 DB 테스트를 건너뜀")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)
