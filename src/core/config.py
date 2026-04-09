from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Biometric Identity SDK"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://dev:dev@localhost:5432/biometric"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.85
    MIN_CONFIDENCE_THRESHOLD: float = 0.5
    MAX_CONFIDENCE_THRESHOLD: float = 0.99

    API_KEY_PREFIX: str = "bsk_live_"
    ENROLL_RATE_LIMIT_PER_MINUTE: int = 10
    MAX_REQUEST_BODY_BYTES: int = 10_485_760  # 10 MB

    RATE_LIMIT_PER_MINUTE: int = 60

    CORS_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = False
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = ["Authorization", "Content-Type", "X-API-Key"]

    EMBEDDING_MODEL_NAME: str = "face Recognition"
    EMBEDDING_DIMENSION: int = 512

    @model_validator(mode="after")
    def validate_cors(self) -> "Settings":
        if "*" in self.CORS_ORIGINS:
            self.CORS_ALLOW_CREDENTIALS = False
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
