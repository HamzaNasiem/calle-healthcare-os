
from pydantic import BaseModel, ConfigDict


class GenericResponseData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str | None = None

class GenericResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    success: bool
    data: GenericResponseData | None = None
