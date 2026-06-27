"""Controlled autonomy: approval gates.

The system runs autonomously by default but *pauses for a human* at defined
gates. The policy:

* **interactive mode** -> prompt the operator at every gate.
* **non-interactive mode** (CI / batch) -> auto-approve, *except* when the
  computed risk is at/above ``approval_required_risk``. In that case the gate
  hard-stops the run and records that human review is required, rather than
  silently proceeding. This is the safety-critical default.
"""

from __future__ import annotations

import sys

from ..config import Settings
from ..logging_config import get_logger
from ..models import ApprovalDecision, ApprovalRecord, RiskLevel, WorkflowState

log = get_logger(__name__)

_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}


class ApprovalRequired(RuntimeError):
    """Raised to halt a non-interactive run that needs human sign-off."""


class ApprovalGate:
    def __init__(self, settings: Settings) -> None:
        self._interactive = settings.interactive
        self._threshold = RiskLevel(settings.approval_required_risk)

    def request(
        self,
        *,
        gate: str,
        state: WorkflowState,
        summary: str,
        risk: RiskLevel = RiskLevel.LOW,
    ) -> ApprovalRecord:
        """Evaluate a gate and return the recorded decision.

        Raises :class:`ApprovalRequired` if a non-interactive run hits a gate
        whose risk meets the human-review threshold.
        """
        if self._interactive:
            decision = self._prompt(gate, summary, risk)
        elif _RISK_ORDER[risk] >= _RISK_ORDER[self._threshold]:
            log.warning("Gate '%s' requires human approval (risk=%s) — halting.",
                        gate, risk.value)
            record = ApprovalRecord(
                gate=gate, decision=ApprovalDecision.REJECTED,
                note=f"Halted: risk {risk.value} >= threshold {self._threshold.value}; "
                     "re-run with --interactive to review.")
            state.approvals.append(record)
            raise ApprovalRequired(record.note)
        else:
            decision = ApprovalRecord(
                gate=gate, decision=ApprovalDecision.AUTO_APPROVED,
                note=f"Auto-approved (risk={risk.value} < {self._threshold.value}).")

        state.approvals.append(decision)
        return decision

    def _prompt(self, gate: str, summary: str, risk: RiskLevel) -> ApprovalRecord:
        print(f"\n=== APPROVAL GATE: {gate} (risk={risk.value}) ===", file=sys.stderr)
        print(summary, file=sys.stderr)
        try:
            answer = input("Approve? [y/N] ").strip().lower()
        except EOFError:
            answer = "n"
        if answer in {"y", "yes"}:
            return ApprovalRecord(gate=gate, decision=ApprovalDecision.APPROVED)
        return ApprovalRecord(gate=gate, decision=ApprovalDecision.REJECTED,
                              note="Operator declined.")
