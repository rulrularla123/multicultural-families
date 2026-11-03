"""US-01 공유 Attachment 모델의 서버 자체 점검. 공식 acceptance 테스트와 구분한다."""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError

from app.models import Attachment, PreparationCase


@pytest.fixture(autouse=True)
def clear_attachments(engine):
    # 기존 반려 fixture가 준비 건을 초기화하기 전에 자식 행을 먼저 지운다.
    with engine.begin() as connection:
        connection.execute(delete(Attachment))
    yield
    with engine.begin() as connection:
        connection.execute(delete(Attachment))


def test_us01_attachment_links_case_and_leaves_text_unextracted(factory):
    with factory.begin() as session:
        attachment = Attachment(case_id=1003, filename="모의서류.pdf", size_bytes=12)
        session.add(attachment)
        session.flush()
        attachment_id = attachment.id
    with factory() as session:
        attachment = session.get(Attachment, attachment_id)
        assert attachment.case_id == 1003
        assert attachment.filename == "모의서류.pdf"
        assert attachment.size_bytes == 12
        assert attachment.document_version == 1
        assert attachment.extracted_text is None
        assert session.get(PreparationCase, 1003).status == "준비중"


def test_us01_attachment_accepts_exact_ten_megabytes(factory):
    with factory.begin() as session:
        session.add(Attachment(case_id=1003, filename="boundary.pdf", size_bytes=10_485_760))
    with factory() as session:
        assert session.scalar(select(Attachment)).size_bytes == 10_485_760


@pytest.mark.parametrize("size", [-1, 10_485_761])
def test_us01_attachment_rejects_out_of_range_metadata(factory, size):
    with pytest.raises(DBAPIError):
        with factory.begin() as session:
            session.add(Attachment(case_id=1003, filename="invalid.pdf", size_bytes=size))
    with factory() as session:
        assert session.scalar(select(Attachment)) is None


def test_us01_attachment_rejects_missing_parent(factory):
    with pytest.raises(DBAPIError):
        with factory.begin() as session:
            session.add(Attachment(case_id=999999, filename="orphan.pdf", size_bytes=12))
    with factory() as session:
        assert session.scalar(select(Attachment)) is None


def test_us01_attachment_rejects_invalid_document_version(factory):
    with pytest.raises(DBAPIError):
        with factory.begin() as session:
            session.add(Attachment(case_id=1003, filename="version.pdf", size_bytes=12, document_version=0))


def test_us01_parent_delete_does_not_silently_delete_attachments(factory):
    with factory.begin() as session:
        session.add(Attachment(case_id=1003, filename="preserve.pdf", size_bytes=12))
    with pytest.raises(DBAPIError):
        with factory.begin() as session:
            session.execute(delete(PreparationCase).where(PreparationCase.id == 1003))
    with factory() as session:
        assert session.get(PreparationCase, 1003) is not None
        assert session.scalar(select(Attachment)).filename == "preserve.pdf"
