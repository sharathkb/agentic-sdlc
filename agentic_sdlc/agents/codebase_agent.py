"""Codebase-reasoning agent (brownfield).

Given a normalised requirement that changes an existing system, identifies the
impacted components, data flows, integration points and overall blast radius.

In a fuller build this agent would be handed a repository map / AST index; here
it reasons from the requirement and any architecture notes in the workflow
context. The interface is designed so a real code-index tool can be injected
later without changing callers.
"""

from __future__ import annotations

from ..models import CodebaseAnalysis, NormalizedRequirement
from .base import BaseAgent

_SYSTEM = """You are reasoning about how a requirement affects an EXISTING
codebase. Identify impacted components (service|module|api|datastore|config),
whether each is added/modified/removed and why, the affected data flows,
integration points, and the overall blast radius (low|medium|high).

Respond with ONLY JSON: impacted_components[{name, kind, change_type, rationale}],
data_flows[], integration_points[], blast_radius."""


class CodebaseAgent(BaseAgent):
    name = "codebase"

    def run(self, requirement: NormalizedRequirement,
            architecture_notes: str = "") -> CodebaseAnalysis:
        self.log.info("Reasoning about codebase impact.")
        user = (f"Requirement title: {requirement.title}\n"
                f"Summary: {requirement.summary}\n"
                f"Functional: {requirement.functional_requirements}\n"
                f"Known architecture notes:\n{architecture_notes or '(none provided)'}")
        analysis = self._complete_model(
            system=_SYSTEM, user=user, tag="codebase",
            schema=CodebaseAnalysis, use_planner=True)
        self.log.info("Impact: %d components, blast radius %s.",
                      len(analysis.impacted_components), analysis.blast_radius.value)
        return analysis
