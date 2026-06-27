"""Workflow orchestrator — the coordination engine.

Responsibilities:

* Drive the phases: understand -> (codebase) -> decompose -> execute -> validate
  -> approve -> summarise.
* Execute the task DAG **level by level**, running independent tasks in a level
  concurrently, and respecting joins (a task waits for *all* parents).
* **Error handling & recovery**: per-task retries with exponential backoff;
  on permanent failure the task is marked FAILED and its descendants are
  SKIPPED rather than crashing the whole run (graceful degradation).
* **Controlled autonomy**: pause at approval gates; halt non-interactive runs
  that exceed the risk threshold.
* Checkpoint state to disk after every phase.

This is deliberately a hand-written orchestrator (rather than a framework) so
the control flow is fully visible and auditable.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from ..agents import (CodebaseAgent, CodegenAgent, DecompositionAgent,
                      RequirementAgent, SummaryAgent, ValidationAgent)
from ..config import Settings, get_settings
from ..guardrails import sanitize_requirement, scan_artifacts_for_secrets
from ..hitl.approval import ApprovalGate, ApprovalRequired
from ..llm import LLMClient, build_llm
from ..logging_config import get_logger
from ..models import (ProjectKind, RiskLevel, Task, TaskResult, TaskStatus,
                      TaskType, WorkflowState)
from ..tools import SafeWorkspace
from .dag import TaskGraph
from .state import save_checkpoint

# Task types that actually emit artifacts via the codegen agent.
_PRODUCING = {TaskType.CODE, TaskType.SCHEMA, TaskType.TEST, TaskType.DOCS}


class Orchestrator:
    def __init__(self, settings: Settings | None = None,
                 llm: LLMClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or build_llm(self.settings)
        self.run_id = uuid.uuid4().hex[:12]
        self.log = get_logger("orchestrator", self.run_id)

        self.workspace = SafeWorkspace(self.settings.output_dir)
        self.checkpoint_dir = self.settings.output_dir + "/checkpoints"

        # Agents (constructed once, share the LLM client).
        self.requirement_agent = RequirementAgent(self.llm, self.settings, self.run_id)
        self.codebase_agent = CodebaseAgent(self.llm, self.settings, self.run_id)
        self.decompose_agent = DecompositionAgent(self.llm, self.settings, self.run_id)
        self.codegen_agent = CodegenAgent(self.llm, self.settings, self.run_id)
        self.validation_agent = ValidationAgent(self.llm, self.settings, self.run_id)
        self.summary_agent = SummaryAgent(self.llm, self.settings, self.run_id)
        self.gate = ApprovalGate(self.settings)

    # ===================================================================== #
    def run(self, raw_requirement: str) -> WorkflowState:
        clean, warnings = sanitize_requirement(raw_requirement)
        state = WorkflowState(run_id=self.run_id, raw_requirement=clean)
        if warnings:
            for w in warnings:
                self.log.warning(w)
            state.context["input_warnings"] = warnings

        self.log.info("=== Run %s starting ===", self.run_id)

        # Phase 1 — understand ------------------------------------------------
        state.requirement = self.requirement_agent.run(clean)
        self._checkpoint(state)

        # Phase 2 — codebase reasoning (brownfield only) ----------------------
        if state.requirement.kind is ProjectKind.BROWNFIELD:
            state.codebase = self.codebase_agent.run(state.requirement)
            self._checkpoint(state)

        # Gate A — proceed past understanding. Ambiguous work is high-risk and
        # forces human sign-off before any code is generated.
        understanding_risk = (
            RiskLevel.HIGH if state.requirement.is_ambiguous else RiskLevel.LOW
        )
        self.gate.request(
            gate="post-understanding",
            state=state,
            summary=self._understanding_brief(state),
            risk=understanding_risk,
        )

        # Phase 3 — decompose -------------------------------------------------
        state.plan = self.decompose_agent.run(state.requirement)
        graph = TaskGraph(state.plan)  # validates DAG / raises on cycles
        state.context["levels"] = graph.levels
        self.log.info("Execution plan has %d levels: %s", len(graph.levels),
                      graph.levels)
        self._checkpoint(state)

        # Phase 4 — execute the DAG ------------------------------------------
        self._execute_graph(graph, state)
        self._checkpoint(state)

        # Phase 5 — validate (reason + run tests) ----------------------------
        state.validation = self.validation_agent.run(
            state.requirement, self.settings.output_dir)
        secret_findings = scan_artifacts_for_secrets(state.all_artifacts())
        if secret_findings:
            state.context["secret_findings"] = secret_findings
            for f in secret_findings:
                self.log.error("SECRET GUARDRAIL: %s", f)
        self._checkpoint(state)

        # Gate B — final approval before declaring the run complete ----------
        final_risk = self._final_risk(state)
        try:
            self.gate.request(
                gate="pre-finalize", state=state,
                summary=self._validation_brief(state), risk=final_risk)
        except ApprovalRequired:
            self.log.warning("Run halted for human review at final gate.")
            self._write_reports(state)
            self._checkpoint(state)
            raise

        # Phase 6 — summarise & emit reports ---------------------------------
        state.summary = self.summary_agent.run(state.requirement)
        self._write_reports(state)
        self._checkpoint(state)
        self.log.info("=== Run %s complete ===", self.run_id)
        return state

    # ===================================================================== #
    # DAG execution with retries, recovery and parallelism
    # ===================================================================== #
    def _execute_graph(self, graph: TaskGraph, state: WorkflowState) -> None:
        for tid in graph.tasks:
            state.results.setdefault(tid, TaskResult(task_id=tid))

        for level_idx, level in enumerate(graph.levels):
            self.log.info("--- Level %d: %s ---", level_idx, level)
            runnable, skipped = [], []
            for tid in level:
                task = graph.tasks[tid]
                if self._deps_ok(task, state):
                    runnable.append(task)
                else:
                    skipped.append(tid)

            for tid in skipped:
                state.results[tid].status = TaskStatus.SKIPPED
                state.results[tid].error = "Upstream dependency failed."
                self.log.warning("Task '%s' SKIPPED (dependency failed).", tid)

            # Independent tasks in a level run concurrently.
            max_workers = max(1, min(self.settings.max_parallelism, len(runnable)))
            if not runnable:
                continue
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(self._execute_task, t, state): t
                           for t in runnable}
                for fut in as_completed(futures):
                    fut.result()  # exceptions already captured in TaskResult

    def _deps_ok(self, task: Task, state: WorkflowState) -> bool:
        return all(
            state.results.get(dep, TaskResult(task_id=dep)).status
            == TaskStatus.SUCCEEDED
            for dep in task.depends_on
        )

    def _execute_task(self, task: Task, state: WorkflowState) -> None:
        result = state.results[task.id]
        result.status = TaskStatus.RUNNING
        result.started_at = datetime.now(timezone.utc)

        for attempt in range(1, self.settings.max_retries + 2):
            result.attempts = attempt
            try:
                if task.type in _PRODUCING:
                    prior = state.all_artifacts()
                    artifacts = self.codegen_agent.run(task, state.requirement, prior)
                    for art in artifacts:
                        self.workspace.write_artifact(art)
                    result.artifacts = artifacts
                else:
                    # design / review — coordination nodes, no artifacts.
                    self.log.info("Task '%s' (%s) is a coordination node.",
                                  task.id, task.type.value)
                result.status = TaskStatus.SUCCEEDED
                result.finished_at = datetime.now(timezone.utc)
                return
            except Exception as exc:  # noqa: BLE001 - recorded, then retried/failed
                if attempt <= self.settings.max_retries:
                    delay = self.settings.retry_base_delay * (2 ** (attempt - 1))
                    self.log.warning("Task '%s' attempt %d failed: %s — retrying in %.1fs",
                                     task.id, attempt, exc, delay)
                    time.sleep(delay)
                    continue
                result.status = TaskStatus.FAILED
                result.error = str(exc)
                result.finished_at = datetime.now(timezone.utc)
                self.log.error("Task '%s' FAILED permanently: %s", task.id, exc)
                return

    # ===================================================================== #
    # Risk + reporting helpers
    # ===================================================================== #
    def _final_risk(self, state: WorkflowState) -> RiskLevel:
        order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
        risk = RiskLevel.LOW
        if state.validation:
            risk = state.validation.max_risk
        if state.requirement and state.requirement.is_ambiguous:
            risk = RiskLevel.HIGH
        if state.validation and state.validation.tests_passed is False:
            risk = RiskLevel.HIGH
        if state.context.get("secret_findings"):
            risk = RiskLevel.HIGH
        # Any failed task escalates.
        if any(r.status is TaskStatus.FAILED for r in state.results.values()):
            risk = max([risk, RiskLevel.HIGH], key=lambda r: order[r])
        return risk

    def _understanding_brief(self, state: WorkflowState) -> str:
        r = state.requirement
        lines = [f"Title: {r.title}", f"Kind: {r.kind.value}", f"Summary: {r.summary}"]
        if r.ambiguities:
            lines.append("Ambiguities (proceeding on assumed answers):")
            lines += [f"  - {a.question} -> {a.assumed_answer}" for a in r.ambiguities]
        return "\n".join(lines)

    def _validation_brief(self, state: WorkflowState) -> str:
        v = state.validation
        n_art = len(state.all_artifacts())
        lines = [f"Artifacts generated: {n_art}",
                 f"Tests passed: {v.tests_passed if v else 'n/a'}",
                 f"Max risk: {self._final_risk(state).value}"]
        if v:
            lines += [f"Risk: [{rk.level.value}] {rk.description}" for rk in v.risks]
        return "\n".join(lines)

    def _write_reports(self, state: WorkflowState) -> None:
        from .reporting import render_summary, render_validation
        self.workspace.write_text("ENGINEERING_SUMMARY.md", render_summary(state))
        if state.validation:
            self.workspace.write_text("VALIDATION.md", render_validation(state))
        if state.plan:
            self.workspace.write_text("PLAN.json", state.plan.model_dump_json(indent=2))

    def _checkpoint(self, state: WorkflowState) -> None:
        save_checkpoint(state, self.checkpoint_dir)
