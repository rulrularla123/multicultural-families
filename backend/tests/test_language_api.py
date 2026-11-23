"""US-08 서버 언어 기본값과 명시적 한국어 요청."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import documents
from app.core.db import get_session
from app.main import app
from app.services import qa


@pytest.fixture
def client(monkeypatch):
    async def no_db():
        yield None

    monkeypatch.setitem(app.dependency_overrides, get_session, no_db)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(("language", "expected", "greeting"), [
    ({}, "vi", "Xin chào!"),
    ({"lang": "ko"}, "ko", "안녕하세요!"),
])
def test_chat_language(client, monkeypatch, language, expected, greeting):
    monkeypatch.setattr(qa.llm, "record_usage", AsyncMock())

    response = client.post("/api/v1/chat", json={"message": "안녕하세요", **language})

    assert response.status_code == 200, response.text
    assert response.json()["lang"] == expected
    assert response.json()["answer"].startswith(greeting)


@pytest.mark.parametrize(("form", "expected"), [({}, "vi"), ({"lang": "ko"}, "ko")])
def test_upload_passes_language_to_analysis(client, monkeypatch, form, expected):
    create_analysis = AsyncMock(return_value={"lang": expected})
    monkeypatch.setattr(documents.svc, "create_analysis", create_analysis)

    response = client.post(
        "/api/v1/documents",
        headers={"X-Client-Id": "language-test"},
        data=form,
        files={"file": ("sample.pdf", b"test upload", "application/pdf")},
    )

    assert response.status_code == 201, response.text
    create_analysis.assert_awaited_once_with(None, "language-test", "sample.pdf", "application/pdf", b"test upload", expected)
