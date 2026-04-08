from functools import lru_cache

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

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/biometric_sdk"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.85
    MIN_CONFIDENCE_THRESHOLD: float = 0.5
    MAX_CONFIDENCE_THRESHOLD: float = 0.99

    RATE_LIMIT_PER_MINUTE: int = 60

    CORS_ORIGINS: list[str] = ["*"]

    EMBEDDING_MODEL_NAME: str = "face Recognition"
    EMBEDDING_DIMENSION: int = 512


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
