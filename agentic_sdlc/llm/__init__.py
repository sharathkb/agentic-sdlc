"""LLM backend selection.

``build_llm`` returns the real Anthropic client when an API key is present and
mock mode is not forced; otherwise the deterministic offline client. This is
the single decision point for the whole system.
"""

from __future__ import annotations

from ..config import Settings
from ..logging_config import get_logger
from .client import AnthropicLLMClient, LLMClient, LLMError
from .mock import MockLLMClient

log = get_logger(__name__)


def build_llm(settings: Settings) -> LLMClient:
    if settings.force_mock or not settings.anthropic_api_key:
        reason = "forced" if settings.force_mock else "no ANTHROPIC_API_KEY"
        log.info("Using MockLLMClient (%s) — deterministic offline mode.", reason)
        return MockLLMClient()
    log.info("Using AnthropicLLMClient (model=%s, planner=%s).",
             settings.model, settings.planner_model)
    return AnthropicLLMClient(
        api_key=settings.anthropic_api_key,
        default_model=settings.model,
        default_max_tokens=settings.max_tokens,
        max_retries=settings.max_retries,
        base_delay=settings.retry_base_delay,
    )


__all__ = ["LLMClient", "LLMError", "AnthropicLLMClient", "MockLLMClient", "build_llm"]
