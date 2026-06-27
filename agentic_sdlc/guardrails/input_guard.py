"""Input-side guardrails.

The requirement string is untrusted free text. Before it reaches any model we:

* enforce a length cap (cost / abuse control),
* reject empty input,
* neutralise the most common prompt-injection patterns by flagging them.

This is *defence in depth*, not a silver bullet — the system prompt for each
agent is also written to treat the requirement strictly as data to analyse.
"""

from __future__ import annotations

import re

MAX_REQUIREMENT_CHARS = 20_000

# Heuristic patterns that frequently signal an attempt to override instructions.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all|previous|above) instructions", re.I),
    re.compile(r"disregard (the )?(system|previous) prompt", re.I),
    re.compile(r"you are now (a|an|in)\b", re.I),
    re.compile(r"reveal (your )?(system )?prompt", re.I),
]


class GuardrailError(ValueError):
    """Raised when input fails a hard guardrail check."""


def sanitize_requirement(raw: str) -> tuple[str, list[str]]:
    """Validate and lightly normalise a requirement.

    Returns ``(clean_text, warnings)``. Raises :class:`GuardrailError` only on
    hard failures (empty / oversized) so the run can still proceed when the
    input is merely *suspicious* — the warning is surfaced to the human gate.
    """
    if raw is None or not raw.strip():
        raise GuardrailError("Requirement is empty.")
    text = raw.strip()
    if len(text) > MAX_REQUIREMENT_CHARS:
        raise GuardrailError(
            f"Requirement too long ({len(text)} chars > {MAX_REQUIREMENT_CHARS})."
        )
    warnings = [
        f"Possible prompt-injection pattern detected: {p.pattern!r}"
        for p in _INJECTION_PATTERNS if p.search(text)
    ]
    return text, warnings
