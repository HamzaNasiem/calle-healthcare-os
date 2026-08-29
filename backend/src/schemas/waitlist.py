import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict


class WaitlistPatientInfo(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: uuid.UUID
    name: str

class WaitlistEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: uuid.UUID
    patient: WaitlistPatientInfo
    preferred_days: list[str] | None = None
    preferred_time_range: str | None = None
    service_type: str | None = None
    notes: str | None = None
    status: str
    created_at: AwareDatetime

class PaginationMeta(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    page: int
    per_page: int
    total: int
    total_pages: int

class WaitlistListData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    entries: list[WaitlistEntry]
    meta: PaginationMeta

class WaitlistListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: WaitlistListData

class WaitlistCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    patient_id: uuid.UUID
    preferred_days: list[str] | None = None
    preferred_time_range: str | None = None
    service_type: str | None = None
    notes: str | None = None

class WaitlistCreateData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    waitlist_id: uuid.UUID
    status: str

class WaitlistCreateResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: WaitlistCreateData
