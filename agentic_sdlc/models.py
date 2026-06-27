"""Typed domain models shared across the whole pipeline.

Every agent communicates through these Pydantic models rather than free-form
dicts. That gives us three production properties for free:

* **Validation** — malformed LLM output is rejected at the boundary, not deep
  inside the orchestrator.
* **Self-documentation** — the data contract between agents is explicit.
* **Serialisation** — the entire run can be checkpointed to JSON and resumed.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectKind(str, enum.Enum):
    """Which SDLC scenario the requirement falls into."""

    GREENFIELD = "greenfield"      # brand-new feature / system
    BROWNFIELD = "brownfield"      # change to an existing codebase
    AMBIGUOUS = "ambiguous"        # under-specified; needs clarification


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# --------------------------------------------------------------------------- #
# 1. Requirement understanding
# --------------------------------------------------------------------------- #
class Ambiguity(BaseModel):
    """A single point of uncertainty discovered in the requirement."""

    question: str = Field(..., description="What is unclear and must be resolved.")
    why_it_matters: str = Field(..., description="Engineering impact if guessed wrong.")
    assumed_answer: str = Field(
        ..., description="The default the system will proceed with if unresolved."
    )


class NormalizedRequirement(BaseModel):
    """The output of the Requirement-Understanding agent."""

    title: str
    summary: str = Field(..., description="One-paragraph restatement of intent.")
    kind: ProjectKind
    goals: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @property
    def is_ambiguous(self) -> bool:
        return self.kind is ProjectKind.AMBIGUOUS or len(self.ambiguities) >= 3


# --------------------------------------------------------------------------- #
# 2. Codebase reasoning (brownfield)
# --------------------------------------------------------------------------- #
class ImpactedComponent(BaseModel):
    name: str
    kind: str = Field(..., description="service | module | api | datastore | config")
    change_type: str = Field(..., description="add | modify | remove")
    rationale: str


class CodebaseAnalysis(BaseModel):
    """How an existing system is affected (brownfield only)."""

    impacted_components: list[ImpactedComponent] = Field(default_factory=list)
    data_flows: list[str] = Field(default_factory=list)
    integration_points: list[str] = Field(default_factory=list)
    blast_radius: RiskLevel = RiskLevel.LOW


# --------------------------------------------------------------------------- #
# 3. Task decomposition  (forms a DAG)
# --------------------------------------------------------------------------- #
class TaskType(str, enum.Enum):
    DESIGN = "design"
    SCHEMA = "schema"
    CODE = "code"
    TEST = "test"
    DOCS = "docs"
    REVIEW = "review"


class Task(BaseModel):
    """A unit of work in the execution DAG."""

    id: str = Field(..., description="Stable slug, e.g. 'design-architecture'.")
    title: str
    type: TaskType
    description: str
    depends_on: list[str] = Field(
        default_factory=list, description="IDs of tasks that must finish first."
    )
    # What artifact path(s) this task is expected to produce, if any.
    produces: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _slug_only(cls, v: str) -> str:
        if not v or any(c.isspace() for c in v):
            raise ValueError("Task id must be a non-empty slug without whitespace.")
        return v


class TaskPlan(BaseModel):
    tasks: list[Task]

    def by_id(self) -> dict[str, Task]:
        return {t.id: t for t in self.tasks}


# --------------------------------------------------------------------------- #
# 4. Engineering output
# --------------------------------------------------------------------------- #
class Artifact(BaseModel):
    """A generated file (code, schema, test or doc)."""

    path: str = Field(..., description="Repo-relative path, e.g. 'app/main.py'.")
    content: str
    task_id: str = Field(..., description="Which task produced this artifact.")
    language: str = "python"

    @field_validator("path")
    @classmethod
    def _no_traversal(cls, v: str) -> str:
        # Defence in depth — the filesystem tool also enforces this.
        if v.startswith("/") or ".." in v.split("/"):
            raise ValueError(f"Unsafe artifact path: {v!r}")
        return v


# --------------------------------------------------------------------------- #
# 5. Validation & risk
# --------------------------------------------------------------------------- #
class Risk(BaseModel):
    description: str
    level: RiskLevel
    mitigation: str


class ValidationReport(BaseModel):
    risks: list[Risk] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    test_strategy: list[str] = Field(default_factory=list)
    # Populated by actually executing the generated test suite.
    tests_passed: Optional[bool] = None
    test_output: Optional[str] = None

    @property
    def max_risk(self) -> RiskLevel:
        order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
        if not self.risks:
            return RiskLevel.LOW
        return max((r.level for r in self.risks), key=lambda lvl: order[lvl])


# --------------------------------------------------------------------------- #
# Workflow envelope — the single object that threads through the orchestrator
# --------------------------------------------------------------------------- #
class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    error: Optional[str] = None
    artifacts: list[Artifact] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class ApprovalDecision(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


class ApprovalRecord(BaseModel):
    gate: str
    decision: ApprovalDecision
    note: str = ""
    at: datetime = Field(default_factory=_utcnow)


class WorkflowState(BaseModel):
    """Single source of truth for one end-to-end run. Fully serialisable."""

    run_id: str
    raw_requirement: str
    created_at: datetime = Field(default_factory=_utcnow)

    requirement: Optional[NormalizedRequirement] = None
    codebase: Optional[CodebaseAnalysis] = None
    plan: Optional[TaskPlan] = None
    results: dict[str, TaskResult] = Field(default_factory=dict)
    validation: Optional[ValidationReport] = None
    summary: Optional[str] = None
    approvals: list[ApprovalRecord] = Field(default_factory=list)

    # Free-form scratch space agents can read/write (e.g. architecture notes).
    context: dict[str, Any] = Field(default_factory=dict)

    def all_artifacts(self) -> list[Artifact]:
        out: list[Artifact] = []
        for r in self.results.values():
            out.extend(r.artifacts)
        return out
