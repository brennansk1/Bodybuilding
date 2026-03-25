import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_INSECURE_DEFAULT_KEY = "change-me-in-production-use-openssl-rand-hex-32"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://cpos:cpos_dev_password@postgres:5432/cpos"
    SECRET_KEY: str = _INSECURE_DEFAULT_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENVIRONMENT: str = "development"
    # Comma-separated list of allowed CORS origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"
    # DB connection pool settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}

    def validate_for_production(self) -> None:
        """Warn or raise for insecure settings in production."""
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == _INSECURE_DEFAULT_KEY:
                raise RuntimeError(
                    "SECRET_KEY must be changed from the default in production. "
                    "Generate one with: openssl rand -hex 32"
                )
        elif self.SECRET_KEY == _INSECURE_DEFAULT_KEY:
            logger.warning(
                "Using insecure default SECRET_KEY. Set SECRET_KEY env var before deploying."
            )


settings = Settings()
settings.validate_for_production()
