"""Validation & risk agent.

Two halves:

1. **Reasoned** — asks the model for risks, trade-offs and a test strategy.
2. **Empirical** — actually executes the generated test suite via
   :func:`run_pytest` and records the real pass/fail outcome.

The empirical half is what turns "the model says it's fine" into evidence.
"""

from __future__ import annotations

from pathlib import Path

from ..models import NormalizedRequirement, ValidationReport
from ..tools import run_pytest
from .base import BaseAgent

_SYSTEM = """You are performing risk analysis and defining a validation strategy
for a generated implementation. Identify concrete risks (each with level
low|medium|high and a mitigation), key trade-offs, and a test strategy.

Respond with ONLY JSON: risks[{description, level, mitigation}], tradeoffs[],
test_strategy[]."""


class ValidationAgent(BaseAgent):
    name = "validation"

    def run(self, requirement: NormalizedRequirement,
            workspace_dir: str | Path) -> ValidationReport:
        self.log.info("Assessing risks and validation strategy.")
        user = (f"Requirement: {requirement.title}\n"
                f"Summary: {requirement.summary}\n"
                f"Non-functional: {requirement.non_functional_requirements}")
        report = self._complete_model(
            system=_SYSTEM, user=user, tag="validation",
            schema=ValidationReport, use_planner=True)

        # Empirical validation: run the tests that were generated.
        self.log.info("Executing generated test suite for verification.")
        passed, output = run_pytest(workspace_dir)
        report.tests_passed = passed
        report.test_output = output
        self.log.info("Test execution %s.", "PASSED" if passed else "FAILED")
        return report
