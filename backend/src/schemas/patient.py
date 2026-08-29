import uuid
from datetime import date

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class PatientBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    full_name: str = Field(..., max_length=150)
    phone: str = Field(pattern=r"^\+?[1-9]\d{1,14}$")
    is_existing_patient: bool
    visit_count: int
    last_visit_date: date | None = None
    is_vip: bool

class PatientListResponseData(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    id: uuid.UUID
    full_name: str = Field(..., max_length=150)
    phone: str
    dob: str | None = None
    age: int | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    is_existing_patient: bool = True
    visit_count: int = 0
    last_visit_date: date | None = None
    recall_status: str = "up_to_date"
    recall_opted_out: bool = False
    is_vip: bool = False
    created_at: AwareDatetime

class PaginationMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1, le=100)
    total: int
    total_pages: int | None = 1

class PatientListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    data: dict  # Will contain 'patients'
    meta: PaginationMeta

class PatientDetailData(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)
    id: uuid.UUID
    full_name: str = Field(..., max_length=150)
    phone: str
    email: str | None = None
    dob: str | None = Field(None, max_length=50)
    age: int | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_time: str | None = "morning"
    recall_opted_out: bool = False
    recall_status: str = "up_to_date"
    notes: str | None = None
    is_existing_patient: bool = True
    visit_count: int = 0
    last_visit_date: date | None = None
    total_revenue_cents: int = 0
    is_vip: bool = False
    data_access_level: str = Field("standard", max_length=50)
    created_at: AwareDatetime

class PatientDetailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    data: PatientDetailData

class PhiRevealRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reveal_reason: str = Field(..., max_length=255)

class PhiRevealData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str
    phone: str
    dob: str
    reveal_expires_at: AwareDatetime
    audit_log_id: uuid.UUID

class PhiRevealResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    data: PhiRevealData

class PatientAppointmentItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: uuid.UUID
    slot_start: AwareDatetime
    slot_end: AwareDatetime
    status: str
    service_type: str | None = None

class PatientAppointmentsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    appointments: list[PatientAppointmentItem]

class PatientAppointmentsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    data: PatientAppointmentsData

class PatientCallLogItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: uuid.UUID
    created_at: AwareDatetime
    duration_seconds: int
    outcome: str
    has_transcript: bool
    call_type: str | None = "general"
    direction: str | None = "inbound"

class PatientCallLogsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    call_logs: list[PatientCallLogItem]

class PatientCallLogsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    data: PatientCallLogsData

class PatientPriorAuthItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: uuid.UUID
    cpt_code: str | None = None
    cpt_description: str | None = None
    urgency: str | None = "standard"
    auth_status: str | None = "pending"
    calle_task_id: str | None = None
    call_status: str | None = "pending"
    requested_service_date: date | None = None
    denial_reason: str | None = None
    authorization_number: str | None = None
    created_at: AwareDatetime

class PatientPriorAuthsData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prior_auths: list[PatientPriorAuthItem]

class PatientPriorAuthsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    data: PatientPriorAuthsData

class PatientClinicalNoteItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: uuid.UUID
    created_at: AwareDatetime
    authored_by: str
    note: str

class PatientClinicalNotesData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    notes: list[PatientClinicalNoteItem]

class PatientClinicalNotesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    data: PatientClinicalNotesData

class PatientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str = Field(..., max_length=150)
    phone: str = Field(pattern=r"^\+?[1-9]\d{1,14}$")
    dob: str | None = Field(None, max_length=50)
    email: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    notes: str | None = None
    preferred_time: str | None = "morning"
    recall_opted_out: bool | None = False
    is_vip: bool | None = False
    data_access_level: str | None = "standard"

class PatientUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    dob: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_time: str | None = None
    notes: str | None = None
    recall_opted_out: bool | None = None
    is_vip: bool | None = None

class PatientCreateResponseData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    patient_id: uuid.UUID

class PatientCreateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    success: bool
    data: PatientCreateResponseData
