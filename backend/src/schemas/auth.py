import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    email: EmailStr
    password: str

class LoginResponseData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mfa_required: bool
    mfa_setup_needed: bool | None = False
    mfa_token: str | None = None
    user_id: uuid.UUID
    access_token: str | None = None

class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: LoginResponseData

class MfaVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mfa_token: str
    totp_code: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: uuid.UUID
    email: EmailStr
    role: str
    tenant_id: uuid.UUID
    full_name: str

class TokenData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 900
    user: UserResponse | None = None

class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: TokenData

class MfaSetupData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    qr_code_url: str
    manual_entry_key: str
    backup_codes: list[str]

class MfaSetupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: MfaSetupData

class SessionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str
    ip_address: str
    user_agent: str
    created_at: AwareDatetime
    last_active_at: AwareDatetime
    is_current: bool

class SessionsResponseData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sessions: list[SessionInfo]

class SessionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: SessionsResponseData

class MeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    userId: uuid.UUID
    email: EmailStr
    role: str
    clinicId: uuid.UUID
    clinicName: str
    timezone: str
