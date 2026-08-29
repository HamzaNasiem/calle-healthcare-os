import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict


class SmsLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: uuid.UUID
    direction: str
    sms_type: str
    patient_name: str
    status: str
    created_at: AwareDatetime
    content: str
    
class SmsListResponseData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sms_logs: list[SmsLogResponse]
    meta: dict
    
class SmsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: SmsListResponseData
