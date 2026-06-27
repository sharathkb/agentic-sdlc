"""Unit tests for the domain models and their validators/invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_sdlc.models import (
    Ambiguity,
    Artifact,
    NormalizedRequirement,
    ProjectKind,
    Risk,
    RiskLevel,
    Task,
    TaskPlan,
    TaskType,
    ValidationReport,
)


def test_task_id_rejects_whitespace():
    with pytest.raises(ValidationError):
        Task(id="bad id", title="t", type=TaskType.CODE, description="d")


def test_task_id_accepts_slug():
    t = Task(id="api-endpoints", title="t", type=TaskType.CODE, description="d")
    assert t.id == "api-endpoints"
    assert t.depends_on == []


def test_artifact_rejects_absolute_path():
    with pytest.raises(ValidationError):
        Artifact(path="/etc/passwd", content="x", task_id="t")


def test_artifact_rejects_parent_traversal():
    with pytest.raises(ValidationError):
        Artifact(path="../../secrets.txt", content="x", task_id="t")


def test_artifact_accepts_relative_path():
    a = Artifact(path="app/main.py", content="x = 1", task_id="t")
    assert a.path == "app/main.py"
    assert a.language == "python"


def test_taskplan_by_id_indexes_tasks():
    plan = TaskPlan(tasks=[
        Task(id="a", title="A", type=TaskType.DESIGN, description="d"),
        Task(id="b", title="B", type=TaskType.CODE, description="d", depends_on=["a"]),
    ])
    by_id = plan.by_id()
    assert set(by_id) == {"a", "b"}
    assert by_id["b"].depends_on == ["a"]


def test_validation_max_risk_empty_is_low():
    assert ValidationReport().max_risk is RiskLevel.LOW


def test_validation_max_risk_picks_highest():
    report = ValidationReport(risks=[
        Risk(description="x", level=RiskLevel.LOW, mitigation="m"),
        Risk(description="y", level=RiskLevel.HIGH, mitigation="m"),
        Risk(description="z", level=RiskLevel.MEDIUM, mitigation="m"),
    ])
    assert report.max_risk is RiskLevel.HIGH


def test_requirement_is_ambiguous_flag():
    req = NormalizedRequirement(
        title="t", summary="s", kind=ProjectKind.AMBIGUOUS,
        ambiguities=[Ambiguity(question="q?", why_it_matters="w", assumed_answer="a")],
    )
    assert req.is_ambiguous is True

    clear = NormalizedRequirement(title="t", summary="s", kind=ProjectKind.GREENFIELD)
    assert clear.is_ambiguous is False
