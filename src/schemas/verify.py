import base64

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.common import BiometricType


class VerifyRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User identifier to verify against",
    )
    biometric_type: BiometricType = Field(
        ...,
        description="Type of biometric to verify",
    )
    biometric_data: str = Field(
        ...,
        description="Base64-encoded image or biometric data to verify",
    )
    confidence_threshold: float | None = Field(
        default=None,
        ge=0.5,
        le=0.99,
        description="Override default confidence threshold for this verification",
    )
    return_score: bool = Field(
        default=False,
        description="Whether to return the raw similarity score",
    )

    @field_validator("biometric_data")
    @classmethod
    def validate_biometric_data(cls, v: str) -> str:
        try:
            base64.b64decode(v)
        except Exception as e:
            raise ValueError(f"Invalid base64 encoding: {e}") from e
        return v


class VerifyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verified: bool = Field(..., description="Whether verification passed")
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Similarity score between 0 and 1",
    )
    threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Threshold used for verification",
    )
    user_id: str = Field(..., description="User identifier")
    biometric_type: BiometricType = Field(..., description="Type of biometric verified")
    model_version: str = Field(..., description="ML model version used")
    timestamp: str = Field(..., description="Verification timestamp (ISO 8601)")
    liveness_check_passed: bool | None = Field(
        default=None,
        description="Whether liveness check passed (if enabled)",
    )


class BatchVerifyRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of user IDs to verify against",
    )
    biometric_type: BiometricType = Field(
        ...,
        description="Type of biometric to verify",
    )
    biometric_data: str = Field(
        ...,
        description="Base64-encoded biometric data to verify",
    )
    confidence_threshold: float | None = Field(
        default=None,
        ge=0.5,
        le=0.99,
        description="Override default confidence threshold",
    )

    @field_validator("biometric_data")
    @classmethod
    def validate_batch_biometric_data(cls, v: str) -> str:
        try:
            base64.b64decode(v)
        except Exception as e:
            raise ValueError(f"Invalid base64 encoding: {e}") from e
        return v


class BatchVerifyResult(BaseModel):
    user_id: str
    verified: bool
    confidence_score: float


class BatchVerifyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    results: list[BatchVerifyResult] = Field(
        ...,
        description="Verification results for each user",
    )
    biometric_type: BiometricType
    model_version: str
    timestamp: str
