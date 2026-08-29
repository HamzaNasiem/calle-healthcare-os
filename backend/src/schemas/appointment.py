import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class AppointmentPatientInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: uuid.UUID
    full_name: str = Field(..., max_length=150)
    phone: str

class AppointmentProviderInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: uuid.UUID
    display_name: str = Field(..., max_length=150)
    specialty: str | None = Field(None, max_length=100)

class AppointmentBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: uuid.UUID
    slot_start: AwareDatetime
    slot_end: AwareDatetime
    service_type: str | None = Field(None, max_length=100)
    duration_minutes: int | None
    status: str = Field(..., max_length=50)
    booked_by: str = Field(..., max_length=50)
    confirmation_code: str | None
    sms_confirmed: bool
    created_at: AwareDatetime

class AppointmentListItem(AppointmentBase):
    patient: AppointmentPatientInfo
    provider: AppointmentProviderInfo
    model_config = ConfigDict(from_attributes=True)

class AppointmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: dict
    meta: dict


class AppointmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    patient_id: uuid.UUID
    provider_id: uuid.UUID
    slot_start: AwareDatetime
    slot_end: AwareDatetime
    service_type: str = Field(..., max_length=100)
    send_confirmation_sms: bool = True
    

class AppointmentCreateData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    appointment_id: uuid.UUID
    confirmation_code: str
    sms_sent: bool

class AppointmentCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: AppointmentCreateData

class AppointmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: str | None = Field(None, max_length=50)
    cancellation_reason: str | None = Field(None, max_length=255)
    slot_start: AwareDatetime | None = None
    slot_end: AwareDatetime | None = None

class AppointmentDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reason: str = Field(..., max_length=255)

class AppointmentUpdateData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    appointment_id: uuid.UUID
    status: str
    slot_start: AwareDatetime | None = None
    slot_end: AwareDatetime | None = None

class AppointmentUpdateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: AppointmentUpdateData

class AppointmentDetailData(AppointmentBase):
    patient: AppointmentPatientInfo
    provider: AppointmentProviderInfo
    sms_history: list[dict] = []
    rescheduled_from_id: uuid.UUID | None = None
    model_config = ConfigDict(from_attributes=True)

class AppointmentDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: AppointmentDetailData
