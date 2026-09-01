"""Centralized backend configuration.

All configuration is read from environment variables (see `.env.example`).
Nothing else in the backend should call `os.environ` directly — import
`get_settings()` instead, so there is exactly one place that knows how
config is sourced.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Auth
    jarvis_api_token: str = "change-me-to-a-long-random-value"

    # AI provider (unused by the orchestrator until Phase 2)
    anthropic_api_key: str = ""

    # Database (unused until the Postgres-backed memory store lands)
    database_url: str = "postgresql://jarvis:jarvis@localhost:5432/jarvis"

    # Server
    jarvis_host: str = "0.0.0.0"
    jarvis_port: int = 8000
    jarvis_log_level: str = "INFO"

    # CORS
    jarvis_cors_origins: str = "*"

    @property
    def cors_origins(self) -> list[str]:
        if self.jarvis_cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.jarvis_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
