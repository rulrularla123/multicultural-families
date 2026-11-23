"""US-02: 조문 조회 오류와 관련 조문 탐색을 확인한다."""

import pytest
from fastapi.testclient import TestClient

from app.core.db import engine
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
        client.portal.call(engine.dispose)


@pytest.mark.db
@pytest.mark.parametrize("route", ["/api/v1/provisions", "/api/v1/provisions/related"])
def test_missing_provision_returns_404(client, route):
    response = client.get(route, params={"id": "없는법령:J99999"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Provision not found."}


@pytest.mark.db
def test_related_provisions_include_linkable_ids(client):
    response = client.get("/api/v1/provisions/related", params={"id": "출입국관리법:J25"})
    assert response.status_code == 200
    linked = next(item for item in response.json() if item["rel"] == "GUIDES")
    assert linked["direction"] == "incoming"
    detail = client.get("/api/v1/provisions", params={"id": linked["provision_id"]})
    assert detail.status_code == 200
    assert detail.json()["id"] == linked["provision_id"]
