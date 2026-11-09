"""US-02 (정상) 3·(실패·거절) 3: 담당자 기준 등록·변경 (F-02)."""

from sqlalchemy import func, select

import pytest

from app.models import Criterion
from app.seed import DEMO_CRITERION, seed_criteria


OFFICER = {"X-Demo-Account": "demo-officer"}
OWNER = {"X-Demo-Account": "demo-user-1"}

COMMON = {"body": "모의 공통 기준 본문", "source": "모의 출처", "checked_on": "2026-11-09", "is_verified": True}


def criterion_count(factory):
    with factory() as session:
        return session.scalar(select(func.count()).select_from(Criterion))


def test_us02_officer_registers_common_criterion_with_source_and_date(client, factory):
    response = client.post("/criteria", headers=OFFICER, json=COMMON)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["office"] is None
    assert (body["body"], body["source"], body["checked_on"]) == ("모의 공통 기준 본문", "모의 출처", "2026-11-09")
    assert (body["version"], body["support_type"], body["is_verified"]) == (1, "F-6-1", True)
    assert body["needs_office_check"] is False
    assert [item["id"] for item in client.get("/criteria", headers=OFFICER).json()] == [body["id"]]


def test_us02_unverified_office_criterion_is_marked_office_check_needed(client):
    response = client.post("/criteria", headers=OFFICER, json={**COMMON, "office": "모의 관서", "is_verified": False})

    assert response.status_code == 201
    assert response.json()["office"] == "모의 관서"
    assert response.json()["needs_office_check"] is True


@pytest.mark.parametrize("missing", ["body", "source", "checked_on"])
def test_us02_criterion_without_required_field_is_rejected(client, factory, missing):
    before = criterion_count(factory)
    body = {key: value for key, value in COMMON.items() if key != missing}

    assert client.post("/criteria", headers=OFFICER, json=body).status_code == 422
    assert criterion_count(factory) == before


@pytest.mark.parametrize("field", ["body", "source"])
def test_us02_blank_text_is_rejected(client, factory, field):
    before = criterion_count(factory)

    assert client.post("/criteria", headers=OFFICER, json={**COMMON, field: "  \n"}).status_code == 422
    assert criterion_count(factory) == before


def test_us02_update_raises_version_and_keeps_same_id(client, factory):
    created = client.post("/criteria", headers=OFFICER, json=COMMON).json()

    response = client.post(f"/criteria/{created['id']}", headers=OFFICER, json={**COMMON, "body": "바뀐 모의 본문"})

    assert response.status_code == 200
    assert (response.json()["id"], response.json()["version"], response.json()["body"]) == (created["id"], 2, "바뀐 모의 본문")


def test_us02_rejected_update_keeps_existing_criterion(client, factory):
    created = client.post("/criteria", headers=OFFICER, json=COMMON).json()

    assert client.post(f"/criteria/{created['id']}", headers=OFFICER, json={**COMMON, "source": ""}).status_code == 422
    with factory() as session:
        kept = session.get(Criterion, created["id"])
        assert (kept.source, kept.version) == ("모의 출처", 1)


def test_us02_update_missing_criterion_returns_404(client):
    assert client.post("/criteria/999999", headers=OFFICER, json=COMMON).status_code == 404


@pytest.mark.parametrize("headers, status", [({}, 401), ({"X-Demo-Account": "unknown"}, 401), (OWNER, 403)])
def test_us02_only_officer_can_list_register_or_update_criteria(client, factory, headers, status):
    created = client.post("/criteria", headers=OFFICER, json=COMMON).json()
    before = criterion_count(factory)

    assert client.get("/criteria", headers=headers).status_code == status
    assert client.post("/criteria", headers=headers, json=COMMON).status_code == status
    assert client.post(f"/criteria/{created['id']}", headers=headers, json=COMMON).status_code == status
    assert criterion_count(factory) == before
    with factory() as session:
        assert session.get(Criterion, created["id"]).version == 1


def test_us02_unknown_fields_are_rejected(client, factory):
    before = criterion_count(factory)

    assert client.post("/criteria", headers=OFFICER, json={**COMMON, "version": 9}).status_code == 422
    assert criterion_count(factory) == before


def test_demo_seed_adds_one_verified_common_criterion_once(factory):
    with factory.begin() as session:
        assert seed_criteria(session) == 1
    with factory.begin() as session:
        assert seed_criteria(session) == 0
    with factory() as session:
        rows = session.scalars(select(Criterion)).all()
        assert len(rows) == 1
        assert (rows[0].office, rows[0].is_verified, rows[0].version) == (None, True, 1)
        assert rows[0].body == DEMO_CRITERION["body"]
