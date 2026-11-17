"""법령 판(버전) 정보와 최신 판 확인 결과

Revision ID: 0002
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUMNS = [
    ("law_mst", "TEXT"),                     # 법령일련번호(법령MST). 판마다 다르다
    ("law_id", "TEXT"),                      # 법령ID. 판이 바뀌어도 같다
    ("promulgation_no", "TEXT"),             # 공포번호
    ("loaded_at", "TIMESTAMPTZ"),            # 이 판을 DB에 적재한 시각
    ("version_status", "TEXT NOT NULL DEFAULT 'unknown'"),  # current | upcoming | outdated | unknown
    ("version_checked_at", "TIMESTAMPTZ"),   # 최신 판을 마지막으로 확인한 시각
    ("version_checked_source", "TEXT"),      # law.go.kr | legalize-kr
    ("latest_mst", "TEXT"),                  # 확인 당시 시행 중인 판
    ("upcoming_mst", "TEXT"),                # 공포됐지만 시행 전인 판
    ("upcoming_effective_from", "DATE"),
]


def upgrade() -> None:
    for name, kind in COLUMNS:
        op.execute(f"ALTER TABLE legal_documents ADD COLUMN {name} {kind}")
    op.execute(
        "ALTER TABLE legal_documents ADD CONSTRAINT legal_documents_version_status_check "
        "CHECK (version_status IN ('current', 'upcoming', 'outdated', 'unknown'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE legal_documents DROP CONSTRAINT legal_documents_version_status_check")
    for name, _ in reversed(COLUMNS):
        op.execute(f"ALTER TABLE legal_documents DROP COLUMN {name}")
