import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict


class UserEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: uuid.UUID
    email: str
    role: str
    full_name: str
    is_active: bool
    mfa_enabled: bool
    created_at: AwareDatetime

class UserListData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    users: list[UserEntry]

class UserListResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: UserListData

class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    email: str
    role: str
    full_name: str

class CreateUserData(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    user_id: uuid.UUID
    temporary_password: str
    mfa_setup_required: bool

class CreateUserResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    success: bool
    data: CreateUserData
