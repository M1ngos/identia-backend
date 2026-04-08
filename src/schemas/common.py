from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class BiometricType(StrEnum):
    FACE = "face"
    FINGERPRINT = "fingerprint"
    DOCUMENT = "document"


class ActionType(StrEnum):
    ENROLL = "enroll"
    VERIFY = "verify"
    DELETE = "delete"


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        from_attributes=True,
    )


class TimestampMixin(BaseModel):
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")


class PaginationParams(BaseModel):
    skip: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=100, ge=1, le=1000, description="Max records to return")


class HealthResponse(BaseSchema):
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")


class ReadyResponse(BaseSchema):
    status: str = Field(..., description="Readiness status")
    database: str = Field(default="unknown", description="Database connection status")
