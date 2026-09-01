import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict


class BusinessDay(BaseModel):
    model_config = ConfigDict(extra='ignore')
    open: bool = True
    enabled: bool | None = None
    start: str | None = "08:00"
    end: str | None = "18:00"

    def model_post_init(self, __context):
        if self.enabled is not None:
            self.open = self.enabled
        elif self.open is not None:
            self.enabled = self.open

class Provider(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: uuid.UUID
    display_name: str
    title: str | None = None
    specialty: str | None = None
    npi_number: str | None = None
    dea_number: str | None = None
    bio: str | None = None
    is_accepting_patients: bool
    schedule_override: dict | None = None

class Service(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: uuid.UUID
    name: str
    duration_minutes: int
    price_display: str | None = None
    description: str | None = None

class FaqEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: uuid.UUID
    question_type: str
    answer: str

class AiPersona(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str
    tone: str
    greeting: str
    voicemail_message: str

class SettingsData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    tenant_id: uuid.UUID
    business_hours: dict[str, BusinessDay]
    providers: list[Provider]
    services: list[Service]
    faq_entries: list[FaqEntry]
    ai_persona: AiPersona
    transfer_number: str | None = None
    timezone: str
    updated_at: AwareDatetime

class SettingsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: SettingsData

class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    business_hours: dict[str, BusinessDay] | None = None
    ai_persona: dict | None = None
    timezone: str | None = None
    transfer_number: str | None = None

class SettingsUpdateResponseData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    updated_at: AwareDatetime
    cache_invalidated: bool
    retell_prompt_updated: bool

class SettingsUpdateResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: SettingsUpdateResponseData

class CreateProviderRequest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    display_name: str
    title: str | None = None
    specialty: str | None = None
    npi_number: str | None = None
    dea_number: str | None = None
    bio: str | None = None
    is_accepting_patients: bool = True

class CreateProviderResponseData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    provider_id: uuid.UUID

class CreateProviderResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: CreateProviderResponseData

class TestCallRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    phone: str

class TestCallResponseData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    call_id: str
    message: str

class TestCallResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: TestCallResponseData

class CreateFaqRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    question_type: str
    answer: str

class UpdateFaqRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    question_type: str | None = None
    answer: str | None = None

class FaqResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: FaqEntry
