"""Task-decomposition agent.

Breaks the normalised requirement into a set of tasks with explicit
``depends_on`` edges, forming a DAG the orchestrator executes. Encourages a
real dependency graph (e.g. endpoints depend on BOTH schema and persistence)
rather than a flat list.
"""

from __future__ import annotations

from ..models import NormalizedRequirement, TaskPlan
from .base import BaseAgent

_SYSTEM = """You are decomposing an engineering requirement into an executable
plan. Produce 4-8 tasks. Each task has: id (slug, no spaces), title, type
(design|schema|code|test|docs|review), description, depends_on (list of task
ids), produces (list of repo-relative file paths it will create, may be empty).

Rules:
- The graph MUST be acyclic.
- Prefer real dependencies: implementation depends on design; endpoints depend
  on BOTH their schema and persistence tasks; tests depend on the code they
  test; a final 'review' task depends on tests and docs.
- Use lower-case-hyphen ids.

Respond with ONLY JSON: {"tasks": [ ... ]}."""


class DecompositionAgent(BaseAgent):
    name = "decompose"

    def run(self, requirement: NormalizedRequirement) -> TaskPlan:
        self.log.info("Decomposing requirement into tasks.")
        user = (f"Title: {requirement.title}\nKind: {requirement.kind.value}\n"
                f"Goals: {requirement.goals}\n"
                f"Functional: {requirement.functional_requirements}\n"
                f"Non-functional: {requirement.non_functional_requirements}")
        plan = self._complete_model(
            system=_SYSTEM, user=user, tag="decompose",
            schema=TaskPlan, use_planner=True)
        self.log.info("Produced %d tasks.", len(plan.tasks))
        return plan
