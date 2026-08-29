from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ----------------------------------------
# Retell AI Webhook Schemas
# ----------------------------------------

class RetellInboundCallData(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    call_id: str
    agent_id: str
    call_status: str | None = None
    start_timestamp: int | None = None
    from_number: str | None = None
    to_number: str | None = None
    direction: str | None = None

class RetellInboundRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    event: str
    call: RetellInboundCallData


class RetellTranscriptMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    role: str
    content: str

class RetellPostCallData(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    call_id: str
    agent_id: str
    call_type: str | None = None
    from_number: str | None = None
    to_number: str | None = None
    duration_ms: int | None = None
    start_timestamp: int | None = None
    end_timestamp: int | None = None
    transcript: str | None = None
    transcript_object: list[RetellTranscriptMessage] | None = None
    call_analysis: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

class RetellPostCallRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    event: str
    data: RetellPostCallData


class RetellToolRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    call_id: str
    tool_call_id: str | None = None
    name: str | None = None
    args: dict[str, Any]

# ----------------------------------------
# Telnyx Webhook Schemas
# ----------------------------------------

class TelnyxPhoneNumber(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    phone_number: str

class TelnyxSmsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    id: str
    from_: TelnyxPhoneNumber = Field(alias="from")
    to: list[TelnyxPhoneNumber]
    text: str
    direction: str

class TelnyxEventData(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    event_type: str
    payload: TelnyxSmsPayload

class TelnyxWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    data: TelnyxEventData
    meta: dict[str, Any] | None = None
