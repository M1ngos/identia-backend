from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TokenRequest(BaseModel):
    api_key: str = Field(..., min_length=20, description="Full API key")

    @field_validator("api_key")
    @classmethod
    def validate_key_format(cls, v: str) -> str:
        if not v.startswith("bsk_live_"):
            raise ValueError("Invalid API key format")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds")


class ApiKeyCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str | None = Field(default=None, max_length=100)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ApiKeyCreateResponse(BaseModel):
    key_id: str
    key: str = Field(..., description="Plaintext key — shown once only")
    prefix: str
    label: str | None
    expires_at: datetime | None
    created_at: datetime


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key_id: str
    prefix: str
    label: str | None
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
