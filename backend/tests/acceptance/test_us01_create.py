"""US-01 상황 설명과 서류로 준비 건 만들기 — 인수 테스트 (구현 전 작성).

기대값은 backlog.md US-01 인수 조건과 API.md 항목 1·2(docs/api-agreement-hyun731, 36d9f81)에서만 가져온다.
오류 응답 형식은 API.md에서 미정이라, 거절은 "201 아님 + 준비 건 수 그대로 + 응답에 거절한 필드 이름"으로 확인한다.
범위 밖(first-feature 1절): 표시 언어, 다른 이용자 상세 조회 403(2절 5번).

US-01 생성·목록 API가 아직 없어 모듈 전체를 xfail(strict)로 둔다. 서버가 병합돼 통과하면
XPASS가 실패로 보고되므로 그때 이 표시만 지운다. 기대값은 바꾸지 않는다.
"""
import pytest
from sqlalchemy import func, select

from app.models import CaseStatus, PreparationCase


pytestmark = pytest.mark.xfail(reason="US-01 생성·목록 API 미구현 (김민건 작업 전)", strict=True)

OFFICER = {"X-Demo-Account": "demo-officer"}
OWNER = {"X-Demo-Account": "demo-user-1"}
OTHER = {"X-Demo-Account": "demo-user-2"}


@pytest.fixture
def submit(client, pdf_files):
    """API.md 항목 1 요청: POST /cases, multipart (support_type, situation, files)."""
    def _submit(*, headers=OWNER, support_type="F-6-1", situation="체류기간 연장 서류를 확인하고 싶습니다.", files=None):
        files = pdf_files(1) if files is None else files
        return client.post(
            "/cases", headers=headers,
            data={"support_type": support_type, "situation": situation},
            files=[("files", f) for f in files],
        )
    return _submit


def case_count(factory):
    with factory() as session:
        return session.scalar(select(func.count()).select_from(PreparationCase))


def assert_rejected(response, factory, before, field):
    assert response.status_code != 201
    assert case_count(factory) == before
    assert field in response.text


# --- 2절 1번 (정상) -------------------------------------------------------

def test_us01_valid_submission_creates_one_preparing_case_owned_by_submitter(submit, client, factory):
    """US-01 (정상) 1: F-6-1·상황 설명·PDF 1개 → 준비 건 1개, 상태 준비중, 소유자 = 제출한 이용자."""
    before = case_count(factory)

    response = submit()

    assert response.status_code == 201
    body = response.json()
    assert body["ok"] is True
    case = body["case"]
    assert case["status"] == CaseStatus.PREPARING.value
    assert case["owner_id"] == "demo-user-1"
    assert case["support_type"] == "F-6-1"
    assert case["id"] and case["created_at"]
    assert case_count(factory) == before + 1


def test_us01_anonymous_cannot_create_401(submit, client, factory):
    """API.md 항목 1 권한: 계정 없음 401."""
    before = case_count(factory)

    assert submit(headers={}).status_code == 401
    assert case_count(factory) == before


# --- 2절 2번 (정상) 목록 ----------------------------------------------------

def test_us01_new_case_appears_in_owner_list_with_created_at(submit, client):
    """US-01 (정상) 2: 생성 직후 이용자의 목록에 새 건이 생성 일시와 함께 1줄 추가된다."""
    before = client.get("/cases", headers=OWNER).json()

    case = submit().json()["case"]
    after = client.get("/cases", headers=OWNER)

    assert after.status_code == 200
    rows = after.json()
    assert len(rows) == len(before) + 1
    new = [row for row in rows if row["id"] == case["id"]]
    assert len(new) == 1 and new[0]["created_at"] == case["created_at"]


def test_us01_list_shows_only_own_cases(submit, client):
    """API.md 항목 2: 본인 건만. 다른 이용자의 건은 목록에 나오지 않는다."""
    case = submit().json()["case"]

    other_rows = client.get("/cases", headers=OTHER).json()
    assert case["id"] not in [row["id"] for row in other_rows]
    assert all(row["owner_id"] == "demo-user-1" for row in client.get("/cases", headers=OWNER).json())


@pytest.mark.parametrize("headers,status", [({}, 401), (OFFICER, 403)], ids=["anonymous", "officer"])
def test_us01_list_rejects_anonymous_401_and_officer_403(submit, client, headers, status):
    """API.md 항목 2 실패 응답: 계정 없음 401, 담당자 403."""
    assert client.get("/cases", headers=headers).status_code == status


# --- 2절 3번 (경계) ---------------------------------------------------------

@pytest.mark.parametrize("length", [1, 1000])
def test_us01_situation_1_and_1000_characters_accepted(submit, client, situations, length):
    """US-01 (경계) 3: 상황 설명 1자·1,000자는 받는다."""
    assert submit(situation=situations[length]).status_code == 201


@pytest.mark.parametrize("key", ["1000_with_spaces", "1000_with_newlines"])
def test_us01_1000_characters_counting_spaces_and_newlines_accepted(submit, client, counted_situations, key):
    """US-01 (경계) 3 + API.md 항목 1: 공백·줄바꿈을 포함해 1,000자면 받는다."""
    assert submit(situation=counted_situations[key]).status_code == 201


def test_us01_situation_1001_characters_rejected(submit, client, factory, situations):
    """US-01 (경계) 3: 상황 설명 1,001자는 거절한다."""
    before = case_count(factory)
    assert_rejected(submit(situation=situations[1001]), factory, before, "situation")


@pytest.mark.parametrize("key", ["1001_with_spaces", "1001_with_newlines"])
def test_us01_1001_characters_counting_spaces_and_newlines_rejected(submit, client, factory, counted_situations, key):
    """US-01 (경계) 3 + API.md 항목 1: 공백·줄바꿈을 포함해 1,001자면 거절한다."""
    before = case_count(factory)
    assert_rejected(submit(situation=counted_situations[key]), factory, before, "situation")


def test_us01_pdf_exactly_10485760_bytes_accepted(submit, client, pdf_at_limit):
    """US-01 (경계) 3: 파일 정확히 10MB(10,485,760바이트)는 받는다."""
    assert submit(files=[pdf_at_limit]).status_code == 201


def test_us01_pdf_10485761_bytes_rejected(submit, client, factory, pdf_over_limit):
    """US-01 (경계) 3·(실패) 4: 10,485,761바이트 파일은 거절한다."""
    before = case_count(factory)
    assert_rejected(submit(files=[pdf_over_limit]), factory, before, "files")


@pytest.mark.parametrize("count", [1, 5])
def test_us01_one_and_five_files_accepted(submit, client, pdf_files, count):
    """US-01 (경계) 3: 파일 1개·5개는 받는다."""
    assert submit(files=pdf_files(count)).status_code == 201


@pytest.mark.parametrize("count", [0, 6])
def test_us01_zero_and_six_files_rejected(submit, client, factory, pdf_files, count):
    """US-01 (경계) 3·(실패) 4: 파일 0개·6개는 거절한다."""
    before = case_count(factory)
    assert_rejected(submit(files=pdf_files(count)), factory, before, "files")


# --- 2절 4번 (실패·거절) ------------------------------------------------------

def test_us01_pdf_extension_without_signature_rejected(submit, client, factory, fake_pdf):
    """US-01 (실패) 4: 확장자는 .pdf지만 파일 시그니처가 PDF가 아니면 거절한다."""
    before = case_count(factory)
    assert_rejected(submit(files=[fake_pdf]), factory, before, "files")


def test_us01_non_pdf_extension_rejected(submit, client, factory, non_pdf_extension):
    """US-01 (실패) 4: 확장자가 PDF가 아니면 거절한다."""
    before = case_count(factory)
    assert_rejected(submit(files=[non_pdf_extension]), factory, before, "files")


def test_us01_one_bad_file_among_valid_files_rejects_whole_submission(submit, client, factory, pdf_files, fake_pdf):
    """US-01 (실패) 4: 하나라도 있으면 준비 건을 만들지 않는다."""
    before = case_count(factory)
    assert_rejected(submit(files=pdf_files(2) + [fake_pdf]), factory, before, "files")


@pytest.mark.parametrize("index", range(4), ids=["empty", "spaces", "newlines", "mixed"])
def test_us01_blank_situation_rejected(submit, client, factory, blank_situations, index):
    """US-01 (실패) 4: 빈 상황 설명(공백·줄바꿈만 있는 경우 포함)은 거절한다."""
    before = case_count(factory)
    assert_rejected(submit(situation=blank_situations[index]), factory, before, "situation")


@pytest.mark.parametrize("support_type", ["F-6-2", "E-9", ""])
def test_us01_support_type_other_than_f61_rejected(submit, client, factory, support_type):
    """US-01 (실패) 4: F-6-1 외 유형은 거절한다."""
    before = case_count(factory)
    assert_rejected(submit(support_type=support_type), factory, before, "support_type")
