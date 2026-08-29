import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: uuid.UUID
    sequence_number: int
    timestamp: AwareDatetime
    actor_type: str
    actor_email: str | None = None
    actor_role: str | None = None
    action: str
    target_table: str
    target_id: str | None = None
    target_patient_id: str | None = None
    fields_accessed: list[str] | None = None
    before_snapshot: dict | None = None
    after_snapshot: dict | None = None
    ingress_ip: str
    outcome: str
    row_hash: str

class AuditLogsData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    audit_logs: list[AuditLogEntry]
    meta: dict

class AuditLogsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: AuditLogsData

class AuditVerifyData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: str
    total_records_verified: int | None = None
    verification_duration_ms: int | None = None
    last_record_sequence: int | None = None
    last_verified_at: AwareDatetime | None = None
    breach_at_sequence: int | None = None
    breach_detected_at: AwareDatetime | None = None
    incident_created: bool | None = None
    incident_id: uuid.UUID | None = None

class AuditVerifyResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: AuditVerifyData

class BaaEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: uuid.UUID
    vendor_name: str
    signed_date: str
    expiry_date: str | None = None
    status: str
    phi_categories: list[str]
    ai_training_prohibited: bool
    expiry_warning: bool

class BaaRegistryData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    baas: list[BaaEntry]

class BaaRegistryResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: BaaRegistryData

class IncidentEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: uuid.UUID
    severity: str
    incident_type: str
    description: str
    detected_at: AwareDatetime
    phi_encrypted_at_time: bool
    hhs_notification_due: AwareDatetime | None = None
    status: str
    resolved_at: AwareDatetime | None = None

class IncidentsData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    incidents: list[IncidentEntry]

class IncidentsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: IncidentsData

class AuditLogExportData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    download_url: str
    expires_in_seconds: int

class AuditLogExportResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: AuditLogExportData
