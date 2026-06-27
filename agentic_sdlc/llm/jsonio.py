"""Helpers for coercing LLM text into structured JSON.

Models occasionally wrap JSON in ```json fences or add a sentence of preamble
despite instructions. This module recovers the JSON payload defensively so a
stray token doesn't crash a whole run.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class JSONParseError(ValueError):
    pass


def extract_json(text: str) -> Any:
    """Best-effort extraction of a single JSON value from ``text``."""
    text = text.strip()

    # 1. Direct parse — the happy path.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Fenced code block.
    if m := _FENCE.search(text):
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. First balanced {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue

    raise JSONParseError(f"Could not extract JSON from model output: {text[:200]!r}")
