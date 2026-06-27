"""Runtime configuration.

All tunables live here and are driven by environment variables (or a local
``.env`` file). Secrets such as the API key are **never** hard-coded — a core
production guardrail.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM backend -------------------------------------------------------
    # If no key is present the system falls back to the deterministic MockLLMClient.
    # Anthropic backend
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    model: str = "claude-sonnet-4-6"         # worker model (most steps)
    planner_model: str = "claude-opus-4-8"   # planner model (architecture, decomposition)

    # OpenAI-compatible backend (OpenAI, Groq, Google Gemini, Ollama, custom, …)
    # Set OPENAI_API_KEY (or GROQ_API_KEY / GEMINI_API_KEY via server.py mapping)
    # and OPENAI_BASE_URL to select this backend instead of Anthropic.
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    max_tokens: int = 8000
    # Force the deterministic offline backend even if a key is set (great for CI).
    force_mock: bool = False

    # --- Orchestration -----------------------------------------------------
    max_retries: int = 2            # per-task retries on transient failure
    retry_base_delay: float = 1.0   # seconds; exponential backoff base
    max_parallelism: int = 4        # concurrent tasks within a DAG level

    # --- Human-in-the-loop -------------------------------------------------
    # When False, approval gates auto-approve (CI / non-interactive runs).
    interactive: bool = False
    # Risk level at/above which an explicit human approval is *always* required,
    # even in non-interactive mode (the run pauses and exits for review).
    approval_required_risk: str = "high"

    # --- Output ------------------------------------------------------------
    output_dir: str = "output"
    log_level: str = "INFO"
    log_json: bool = False          # structured JSON logs for prod aggregation


_settings: Settings | None = None


def get_settings() -> Settings:
    """Cached accessor so config is parsed exactly once."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
