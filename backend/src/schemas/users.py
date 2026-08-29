import uuid
from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime

class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    email: EmailStr
    role: str
    full_name: str
    password: str

class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: str | None = None
    is_active: bool | None = None
    full_name: str | None = None

class UserInfo(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    id: uuid.UUID
    email: EmailStr
    role: str
    full_name: str
    is_active: bool
    last_login_at: datetime | None = None

class UserListData(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    users: list[UserInfo]

class UserListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    success: bool
    data: UserListData
