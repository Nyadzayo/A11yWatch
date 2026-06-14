from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[3]  # .../backend


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "dev"

    database_url: str = "postgresql+asyncpg://a11ywatch:a11ywatch@localhost:5432/a11ywatch"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-secret-not-for-prod"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60

    scan_page_timeout_seconds: int = 30
    scan_site_timeout_seconds: int = 600
    scan_max_pages: int = 50
    scan_max_retries: int = 2

    worker_concurrency: int = 2
    scheduler_interval_seconds: int = 60
    scheduler_stagger_seconds: int = 30

    healthcheck_ping_url: str = ""
    operator_alert_email: str = ""
    smtp_url: str = ""

    @model_validator(mode="after")
    def _require_strong_secret_in_prod(self) -> "Settings":
        if self.app_env == "production" and (
            not self.jwt_secret or self.jwt_secret == "dev-secret-not-for-prod"
        ):
            raise ValueError("JWT_SECRET must be set to a strong, non-default value in production")
        return self


settings = Settings()
