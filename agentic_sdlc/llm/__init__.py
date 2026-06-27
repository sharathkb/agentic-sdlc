"""LLM backend selection.

``build_llm`` picks the right client based on which key is present:
  1. MockLLMClient          — no key set, or force_mock=True
  2. AnthropicLLMClient     — ANTHROPIC_API_KEY is set
  3. OpenAICompatibleLLMClient — OPENAI_API_KEY is set (covers OpenAI, Groq,
                                 Google Gemini, Ollama, and any custom endpoint)
"""

from __future__ import annotations

from ..config import Settings
from ..logging_config import get_logger
from .client import AnthropicLLMClient, LLMClient, LLMError, OpenAICompatibleLLMClient
from .mock import MockLLMClient

log = get_logger(__name__)


def build_llm(settings: Settings) -> LLMClient:
    has_key = bool(settings.anthropic_api_key or settings.openai_api_key)

    if settings.force_mock or not has_key:
        reason = "forced" if settings.force_mock else "no API key"
        log.info("Using MockLLMClient (%s) — deterministic offline mode.", reason)
        return MockLLMClient()

    if settings.anthropic_api_key:
        log.info("Using AnthropicLLMClient (model=%s, planner=%s).",
                 settings.model, settings.planner_model)
        return AnthropicLLMClient(
            api_key=settings.anthropic_api_key,
            default_model=settings.model,
            default_max_tokens=settings.max_tokens,
            max_retries=settings.max_retries,
            base_delay=settings.retry_base_delay,
        )

    # OpenAI-compatible provider (Groq, Gemini, Ollama, OpenAI, custom …)
    # Override the Anthropic model names so agents don't pass claude-* to Gemini/Groq.
    settings.model = settings.openai_model
    settings.planner_model = settings.openai_model
    log.info("Using OpenAICompatibleLLMClient (base_url=%s, model=%s).",
             settings.openai_base_url, settings.openai_model)
    return OpenAICompatibleLLMClient(
        api_key=settings.openai_api_key or "ollama",
        base_url=settings.openai_base_url,
        default_model=settings.openai_model,
        default_max_tokens=settings.max_tokens,
        max_retries=settings.max_retries,
        base_delay=settings.retry_base_delay,
    )


__all__ = [
    "LLMClient", "LLMError",
    "AnthropicLLMClient", "OpenAICompatibleLLMClient", "MockLLMClient",
    "build_llm",
]
