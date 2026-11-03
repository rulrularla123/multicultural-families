from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_serializer

from .models import CaseStatus


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


class RejectResponse(BaseModel):
    case_id: int
    status: CaseStatus
    reason: str
    rejected_at: datetime

    @field_serializer("rejected_at")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


class CaseDetail(BaseModel):
    id: int
    situation: str
    display_language: str | None
    support_type: str
    status: CaseStatus
    rejection_reason: str | None


class OfficerCaseDetail(CaseDetail):
    analysis_items: list


class CaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    support_type: str
    status: CaseStatus
    owner_id: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


class CreateCaseResponse(BaseModel):
    ok: bool = True
    case: CaseSummary
