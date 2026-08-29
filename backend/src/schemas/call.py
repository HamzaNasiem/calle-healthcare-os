import uuid
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class CallBase(BaseModel):
    model_config = ConfigDict(extra='ignore')
    
class TranscriptMessage(BaseModel):
    model_config = ConfigDict(extra='ignore')
    speaker: str = Field(..., max_length=100)
    text: str = Field(..., max_length=10000)
    timestamp: str | None = None
    role: str | None = None
    sentiment: str | None = None

class CallLogResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: uuid.UUID
    retell_call_id: str | None = Field(None, max_length=255)
    call_date: AwareDatetime
    duration_seconds: int = 0
    direction: str = "inbound"
    call_type: str = "general"
    status: str = "completed"
    outcome: str = Field("completed", max_length=50)
    from_number: str | None = None
    to_number: str | None = None
    tools_invoked: list[str] = []
    patient_id: uuid.UUID | None = None
    patient_name: str | None = Field(None, max_length=150)
    appointment_id: uuid.UUID | None = None
    has_transcript: bool = False
    transcript_accessible: bool = True
    transcript_turns: list[dict[str, Any]] | None = None
    structured_result: dict[str, Any] | None = None
    completion_score: float | None = None
    completion_label: str | None = None
    evidence: Any | None = None
    summary: str | None = None
    recording_url: str | None = None
    recording_purge_scheduled: AwareDatetime | None = None
    recording_purged_at: AwareDatetime | None = None

class CallListResponseData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    calls: list[CallLogResponse]
    meta: dict[str, Any]

class CallListResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')
    success: bool
    data: CallListResponseData

class TranscriptResponseData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    call_id: uuid.UUID
    transcript: list[TranscriptMessage]
    transcript_turns: list[dict[str, Any]] | None = None
    duration_seconds: int = 0
    direction: str = "inbound"
    call_type: str = "general"
    status: str = "completed"
    outcome: str = Field("completed", max_length=50)
    structured_result: dict[str, Any] | None = None
    summary: str | None = None
    completion_score: float | None = None
    completion_label: str | None = None
    evidence: Any | None = None
    recording_url: str | None = None
    recording_purge_scheduled: AwareDatetime | None = None
    recording_purged_at: AwareDatetime | None = None
    audit_log_id: uuid.UUID | None = None

class TranscriptResponse(BaseModel):
    model_config = ConfigDict(extra='ignore')
    success: bool
    data: TranscriptResponseData

