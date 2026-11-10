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


class RelatedOut(BaseModel):
    provision_id: str
    path: str
    rel: str             # REFERENCES | GUIDES
    direction: str       # outgoing: 이 조문이 가리킴 / incoming: 이 조문을 가리킴
    evidence: str | None
