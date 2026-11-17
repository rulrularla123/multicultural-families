from datetime import date, datetime

from pydantic import BaseModel


class ProvisionOut(BaseModel):
    id: str
    document_id: str
    document_title: str          # 한국어 법령명
    doc_type: str                # law | decree | rule | guide
    level: str                   # jo | hang | ho | mok …
    number_label: str            # 제25조(체류기간 연장허가)
    path: str
    full_text_ko: str
    summary_vi: str | None
    summary_ko: str | None
    effective: bool              # 오늘(한국 날짜) 시행 중인지
    effective_from: date | None
    effective_to: date | None
    status: str
    source_url: str | None
    reviewed: bool = False
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    # 판(버전) 정보. 적재한 판과 국가법령정보센터 공식 링크, 최신 판 확인 결과
    law_mst: str | None = None             # 법령일련번호
    issued_date: date | None = None        # 공포일
    promulgation_no: str | None = None     # 공포번호
    version_url: str | None = None         # 적재한 바로 그 판의 공식 원문
    official_url: str | None = None        # 지금 시행 중인 판의 이 조문 (국가법령정보센터)
    loaded_at: datetime | None = None
    version_status: str = "unknown"        # current | upcoming | outdated | unknown
    version_checked_at: datetime | None = None
    version_checked_source: str | None = None
    upcoming_effective_from: date | None = None
    version_warning: str | None = None     # outdated | unchecked | None


class RelatedOut(BaseModel):
    provision_id: str
    path: str
    rel: str             # REFERENCES | GUIDES
    direction: str       # outgoing: 이 조문이 가리킴 / incoming: 이 조문을 가리킴
    evidence: str | None
