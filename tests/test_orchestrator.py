"""End-to-end orchestrator tests, driven entirely by the deterministic mock LLM.

These exercise the full control flow — understand, decompose, DAG execution,
validation (which actually runs the generated pytest suite), risk escalation and
the human-approval gates — without any network access or credentials.
"""

from __future__ import annotations

import pytest

from agentic_sdlc.config import Settings
from agentic_sdlc.hitl.approval import ApprovalRequired
from agentic_sdlc.models import ProjectKind, RiskLevel, TaskStatus
from agentic_sdlc.orchestration.orchestrator import Orchestrator

URL_SHORTENER = (
    "Build a scalable URL shortener service with APIs, persistence, and analytics."
)
BROWNFIELD = "Add rate limiting to the existing URL shortener API to prevent abuse."
AMBIGUOUS = "Make the service better and faster."


def _settings(tmp_path, **overrides) -> Settings:
    base = dict(force_mock=True, interactive=False, output_dir=str(tmp_path))
    base.update(overrides)
    return Settings(**base)


def test_url_shortener_end_to_end(tmp_path):
    orch = Orchestrator(settings=_settings(tmp_path))
    state = orch.run(URL_SHORTENER)

    # Requirement understood as greenfield.
    assert state.requirement is not None
    assert state.requirement.kind is ProjectKind.GREENFIELD

    # The DAG produced parallel levels and a real join node.
    levels = state.context["levels"]
    assert any(len(level) > 1 for level in levels), "expected a parallel level"

    # All tasks succeeded.
    statuses = {tid: r.status for tid, r in state.results.items()}
    assert all(s is TaskStatus.SUCCEEDED for s in statuses.values()), statuses

    # A runnable FastAPI app was generated.
    paths = {a.path for a in state.all_artifacts()}
    assert "app/main.py" in paths
    assert "tests/test_api.py" in paths

    # Validation actually executed the generated tests and they passed.
    assert state.validation is not None
    assert state.validation.tests_passed is True

    # Reports were written to disk.
    assert (tmp_path / "ENGINEERING_SUMMARY.md").exists()
    assert (tmp_path / "VALIDATION.md").exists()
    assert (tmp_path / "PLAN.json").exists()

    # Controlled autonomy: both gates were auto-approved at acceptable risk.
    assert {a.gate for a in state.approvals} == {"post-understanding", "pre-finalize"}


def test_api_endpoints_is_a_join_node(tmp_path):
    orch = Orchestrator(settings=_settings(tmp_path))
    state = orch.run(URL_SHORTENER)
    plan = state.plan.by_id()
    # The endpoints task must depend on BOTH the contract and the persistence
    # layer — this is the cross-step coordination the assignment asks for.
    deps = set(plan["api-endpoints"].depends_on)
    assert {"api-contract", "persistence"}.issubset(deps)


def test_brownfield_runs_codebase_analysis(tmp_path, monkeypatch):
    # The brownfield rate-limit change carries a HIGH risk (in-memory bucket is
    # not shared across pods), so it requires human approval. Approve every gate.
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "y")
    orch = Orchestrator(settings=_settings(tmp_path, interactive=True))
    state = orch.run(BROWNFIELD)
    assert state.requirement.kind is ProjectKind.BROWNFIELD
    # Codebase reasoning phase ran and identified impacted components.
    assert state.codebase is not None
    assert state.codebase.impacted_components
    assert state.validation.tests_passed is True


def test_brownfield_high_risk_halts_without_approval(tmp_path):
    # Non-interactive: the HIGH-risk change must stop for human sign-off rather
    # than auto-completing. This is the safety-critical default.
    orch = Orchestrator(settings=_settings(tmp_path))
    with pytest.raises(ApprovalRequired):
        orch.run(BROWNFIELD)


def test_ambiguous_halts_at_understanding_gate(tmp_path):
    orch = Orchestrator(settings=_settings(tmp_path))
    # Non-interactive + high-risk ambiguity => the run must stop for a human.
    with pytest.raises(ApprovalRequired):
        orch.run(AMBIGUOUS)


def test_ambiguous_proceeds_when_approved(tmp_path, monkeypatch):
    # Simulate a human approving every gate.
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "y")
    orch = Orchestrator(settings=_settings(tmp_path, interactive=True))
    state = orch.run(AMBIGUOUS)
    assert state.requirement.kind is ProjectKind.AMBIGUOUS
    # At least three ambiguities were surfaced for the human to weigh.
    assert len(state.requirement.ambiguities) >= 3
    assert state.requirement.is_ambiguous is True
