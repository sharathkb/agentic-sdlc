"""Summary agent.

Produces the final human-readable engineering summary (markdown). The rich,
structured summary file is assembled deterministically by the orchestrator;
this agent contributes the narrative rationale section.
"""

from __future__ import annotations

from ..models import NormalizedRequirement
from .base import BaseAgent

_SYSTEM = """You are writing the narrative rationale for an engineering summary.
Be concise and concrete: explain the implementation approach and why it fits the
requirement. Plain markdown prose, no JSON."""


class SummaryAgent(BaseAgent):
    name = "summary"

    def run(self, requirement: NormalizedRequirement) -> str:
        user = f"title:{requirement.title}\nsummary:{requirement.summary}"
        return self._complete_text(system=_SYSTEM, user=user, tag="summary")
