import base64

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.schemas.common import BiometricType


def _validate_b64_biometric(v: str) -> str:
    """Shared base64 + size validator used by multiple request models."""
    try:
        decoded = base64.b64decode(v, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e
    if len(decoded) < 100:
        raise ValueError("Biometric data too small to be a valid image")
    if len(decoded) > 5 * 1024 * 1024:
        raise ValueError("Biometric data exceeds maximum size of 5 MB")
    return v


class EnrollRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique user identifier from your system",
    )
    biometric_type: BiometricType = Field(
        ...,
        description="Type of biometric to enroll",
    )
    biometric_data: str = Field(
        ...,
        description="Base64-encoded image data (JPEG, PNG) or binary fingerprint data",
    )
    confidence_threshold: float | None = Field(
        default=None,
        ge=0.5,
        le=0.99,
        description="Override default confidence threshold for this enrollment",
    )
    metadata: dict[str, object] | None = Field(
        default=None,
        description="Additional metadata to store with the enrollment",
    )

    @field_validator("biometric_data")
    @classmethod
    def validate_biometric_data(cls, v: str) -> str:
        return _validate_b64_biometric(v)


class EnrollResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enrollment_id: str = Field(..., description="Unique enrollment record ID")
    user_id: str = Field(..., description="User identifier")
    biometric_type: BiometricType = Field(..., description="Type of biometric enrolled")
    embedding_dimension: int = Field(..., description="Dimension of the embedding vector")
    model_version: str = Field(..., description="ML model version used")
    created_at: str = Field(..., description="Enrollment timestamp (ISO 8601)")
    message: str = Field(default="Enrollment successful")


class EnrollUpdateRequest(BaseModel):
    biometric_data: str = Field(
        ...,
        description="New base64-encoded biometric data to replace existing",
    )

    @field_validator("biometric_data")
    @classmethod
    def validate_biometric_data(cls, v: str) -> str:
        return _validate_b64_biometric(v)


class EnrollDeleteResponse(BaseModel):
    message: str = Field(default="Enrollment deleted successfully")
    user_id: str
    biometric_type: str


class EnrollListItem(BaseModel):
    """Summary of a single enrollment returned by the list endpoint."""

    model_config = ConfigDict(from_attributes=True)

    enrollment_id: str = Field(..., description="Unique enrollment record ID")
    user_id: str = Field(..., description="User identifier")
    biometric_type: BiometricType = Field(..., description="Type of biometric enrolled")
    embedding_dimension: int = Field(..., description="Dimension of the embedding vector")
    model_version: str = Field(..., description="ML model version used")
    created_at: str = Field(..., description="Enrollment timestamp (ISO 8601)")
