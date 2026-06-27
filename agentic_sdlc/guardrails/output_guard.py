"""Output-side guardrails.

Generated code is scanned for obvious hard-coded secrets before it is written
to disk or shown to a human. Catching these here prevents the system from
"helpfully" committing an API key the model hallucinated into a config file.
"""

from __future__ import annotations

import re

from ..models import Artifact

# Conservative, low-false-positive patterns.
_SECRET_PATTERNS = {
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{40,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key_block": re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    "generic_assignment": re.compile(
        r"(?i)(password|secret|api[_-]?key|token)\s*=\s*['\"][^'\"]{8,}['\"]"
    ),
}


def scan_artifacts_for_secrets(artifacts: list[Artifact]) -> list[str]:
    """Return a list of human-readable findings (empty == clean)."""
    findings: list[str] = []
    for art in artifacts:
        for name, pat in _SECRET_PATTERNS.items():
            if pat.search(art.content):
                findings.append(f"{art.path}: possible {name} detected")
    return findings
