"""LLM client abstraction.

The orchestrator depends on the :class:`LLMClient` *protocol*, not on Anthropic
directly. This dependency-inversion buys us:

* **Testability / offline runs** — :class:`~agentic_sdlc.llm.mock.MockLLMClient`
  returns deterministic fixtures, so the entire workflow runs in CI with no key.
* **Swappability** — a different provider can be dropped in without touching
  agent code.

The real client adds production hygiene: timeouts, bounded retries with
exponential backoff + jitter on transient errors, and a hard distinction
between retryable (5xx / overload / network) and non-retryable (4xx) failures.
"""

from __future__ import annotations

import random
import time
from typing import Protocol, runtime_checkable

from ..logging_config import get_logger

log = get_logger(__name__)


class LLMError(RuntimeError):
    """Raised when the model call ultimately fails (after retries)."""


@runtime_checkable
class LLMClient(Protocol):
    """Minimal surface the agents rely on."""

    def complete(
        self,
        *,
        system: str,
        user: str,
        tag: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return the model's text completion.

        ``tag`` names the calling stage (e.g. ``"decompose"``). The real client
        ignores it; the mock uses it to select a fixture.
        """
        ...


class AnthropicLLMClient:
    """Production client wrapping the official ``anthropic`` SDK."""

    def __init__(
        self,
        api_key: str,
        default_model: str,
        default_max_tokens: int,
        max_retries: int = 2,
        base_delay: float = 1.0,
        timeout: float = 120.0,
    ) -> None:
        # Imported lazily so the package works without the SDK installed
        # (e.g. mock-only / offline environments).
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - env dependent
            raise LLMError(
                "The 'anthropic' package is required for live runs. "
                "Install it or run in mock mode (AGENTIC_FORCE_MOCK=1)."
            ) from exc

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self._default_model = default_model
        self._default_max_tokens = default_max_tokens
        self._max_retries = max_retries
        self._base_delay = base_delay

    def _is_retryable(self, exc: Exception) -> bool:
        a = self._anthropic
        retryable = (
            getattr(a, "APIConnectionError", ()),
            getattr(a, "RateLimitError", ()),
            getattr(a, "InternalServerError", ()),
        )
        return isinstance(exc, tuple(t for t in retryable if isinstance(t, type)))

    def complete(
        self,
        *,
        system: str,
        user: str,
        tag: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        model = model or self._default_model
        max_tokens = max_tokens or self._default_max_tokens
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                # Concatenate text blocks (ignore any non-text blocks defensively).
                return "".join(
                    block.text for block in resp.content
                    if getattr(block, "type", None) == "text"
                )
            except Exception as exc:  # noqa: BLE001 - we re-raise selectively
                if attempt > self._max_retries or not self._is_retryable(exc):
                    raise LLMError(f"[{tag}] model call failed: {exc}") from exc
                delay = self._base_delay * (2 ** (attempt - 1))
                delay += random.uniform(0, delay * 0.25)  # jitter
                log.warning("[%s] transient error (attempt %d), retrying in %.1fs: %s",
                            tag, attempt, delay, exc)
                time.sleep(delay)
