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

    # Database
    database_url: str = "postgresql://jarvis:jarvis@localhost:5432/jarvis"

    # Server
    jarvis_host: str = "0.0.0.0"
    jarvis_port: int = 8000
    jarvis_log_level: str = "INFO"

    # CORS
    jarvis_cors_origins: str = "*"

    # --- Phase 2: model routing (agent/provider/router.py) ---
    # Model IDs are read from config, never hard-coded past this point.
    jarvis_model_primary: str = "claude-sonnet-5"
    jarvis_model_fast: str = "claude-haiku-4-5-20251001"
    jarvis_model_fallback: str = "claude-opus-5"
    claude_max_tokens: int = 4096
    claude_timeout_seconds: float = 30.0
    claude_max_retries: int = 2

    # --- Phase 2: cost/token budget (backend/app/cost) ---
    # Soft daily budget in USD. Advisory, not a hard cutoff: see CostTracker.
    token_budget_daily_usd: float = 5.0

    # --- Phase 2: knowledge deduplication (backend/app/knowledge) ---
    knowledge_similarity_threshold: float = 0.82
    knowledge_min_confidence_to_skip_claude: float = 0.85

    # --- Phase 2: which backing stack to attempt ---
    # Both default to True (attempt the real thing); deps.py falls back to
    # the Phase 1 in-memory/stub stack and logs a warning if unreachable/
    # unconfigured, rather than crashing the backend. Set to False to force
    # Phase 1 behavior deliberately (e.g. offline development).
    jarvis_use_postgres: bool = True
    jarvis_use_claude: bool = True

    # --- Phase 2: feature flags (see docs/DECISIONS.md, "Feature flags") ---
    # Off by default unless noted: these gate experimental or
    # potentially-costly systems so they can be toggled without a code
    # change or redeploy.
    feature_model_routing: bool = True
    feature_auto_knowledge_extraction: bool = True
    feature_context_compression: bool = True
    feature_proactive_suggestions: bool = True
    feature_proactive_learning: bool = False

    # --- Phase 2: prompt templates (/prompts at repo root) ---
    # Empty string = auto-detect (repo_root/prompts, resolved relative to
    # this file); set explicitly if the deployment layout differs (e.g. a
    # container image that doesn't mirror the monorepo path).
    prompts_dir: str = ""

    @property
    def cors_origins(self) -> list[str]:
        if self.jarvis_cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.jarvis_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
