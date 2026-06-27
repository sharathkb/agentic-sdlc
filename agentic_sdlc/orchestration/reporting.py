"""Deterministic rendering of the final markdown reports.

Kept separate from the orchestrator so the report format can evolve without
touching control flow, and so it can be unit-tested directly.
"""

from __future__ import annotations

from ..models import TaskStatus, WorkflowState


def render_summary(state: WorkflowState) -> str:
    r = state.requirement
    v = state.validation
    lines: list[str] = []
    a = lines.append

    a(f"# Engineering Summary — {r.title if r else state.run_id}")
    a("")
    a(f"- **Run id**: `{state.run_id}`")
    a(f"- **Requirement kind**: {r.kind.value if r else 'unknown'}")
    a(f"- **Created**: {state.created_at.isoformat()}")
    a("")

    a("## 1. Requirement & Rationale")
    if r:
        a(r.summary)
        a("")
        if r.goals:
            a("**Goals**: " + "; ".join(r.goals))
        if r.non_goals:
            a("**Non-goals**: " + "; ".join(r.non_goals))
    if state.summary:
        a("")
        a(state.summary)
    a("")

    if r and r.ambiguities:
        a("## 2. Ambiguities & Assumptions")
        for amb in r.ambiguities:
            a(f"- **Q:** {amb.question}")
            a(f"  - *Why it matters:* {amb.why_it_matters}")
            a(f"  - *Assumed:* {amb.assumed_answer}")
        a("")

    if state.codebase:
        a("## 3. Codebase Impact (Brownfield)")
        for c in state.codebase.impacted_components:
            a(f"- `{c.name}` ({c.kind}, {c.change_type}): {c.rationale}")
        a(f"- **Blast radius**: {state.codebase.blast_radius.value}")
        a("")

    a("## 4. Implementation Plan")
    if state.plan:
        for t in state.plan.tasks:
            deps = ", ".join(t.depends_on) or "—"
            res = state.results.get(t.id)
            status = res.status.value if res else "pending"
            a(f"- **{t.id}** [{t.type.value}] ({status}) — {t.title}; depends on: {deps}")
    if levels := state.context.get("levels"):
        a("")
        a(f"Execution levels (parallelism within a level): `{levels}`")
    a("")

    a("## 5. Generated Artifacts")
    arts = state.all_artifacts()
    if arts:
        for art in sorted(arts, key=lambda x: x.path):
            a(f"- `{art.path}` (from `{art.task_id}`)")
    else:
        a("_No file artifacts (coordination-only run)._")
    a("")

    a("## 6. Validation & Risk")
    if v:
        a(f"- **Tests passed**: {v.tests_passed}")
        a(f"- **Max risk**: {v.max_risk.value}")
        for risk in v.risks:
            a(f"  - [{risk.level.value}] {risk.description} — *mitigation:* {risk.mitigation}")
    a("")

    a("## 7. Approvals (Controlled Autonomy)")
    for ap in state.approvals:
        note = f" — {ap.note}" if ap.note else ""
        a(f"- `{ap.gate}`: **{ap.decision.value}**{note}")
    a("")

    failed = [t for t, res in state.results.items() if res.status is TaskStatus.FAILED]
    if failed:
        a("## 8. Failures")
        a(f"Failed tasks: {failed}")
    return "\n".join(lines) + "\n"


def render_validation(state: WorkflowState) -> str:
    v = state.validation
    if v is None:
        return "# Validation\n\n_No validation report._\n"
    lines = ["# Validation Report", "",
             f"**Tests passed:** {v.tests_passed}", "", "## Risks"]
    for r in v.risks:
        lines.append(f"- **[{r.level.value}]** {r.description}")
        lines.append(f"  - Mitigation: {r.mitigation}")
    lines += ["", "## Trade-offs"] + [f"- {t}" for t in v.tradeoffs]
    lines += ["", "## Test Strategy"] + [f"- {s}" for s in v.test_strategy]
    if v.test_output:
        lines += ["", "## Test Execution Output", "```", v.test_output[:4000], "```"]
    return "\n".join(lines) + "\n"
