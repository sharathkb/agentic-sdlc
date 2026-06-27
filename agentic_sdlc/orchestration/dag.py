"""Task dependency graph.

Wraps a :class:`TaskPlan` with graph operations the orchestrator needs:

* **validation** — every dependency exists; the graph is acyclic.
* **levels** — a topological grouping where each level may run in parallel and
  every level depends only on earlier ones. This is what lets the orchestrator
  do real cross-step coordination (a join node waits for *all* its parents)
  instead of naive linear execution.
"""

from __future__ import annotations

from ..models import Task, TaskPlan


class DagError(ValueError):
    pass


class TaskGraph:
    def __init__(self, plan: TaskPlan) -> None:
        self.tasks: dict[str, Task] = plan.by_id()
        if len(self.tasks) != len(plan.tasks):
            raise DagError("Duplicate task ids in plan.")
        self._validate_edges()
        self._levels = self._compute_levels()

    # ------------------------------------------------------------------ #
    def _validate_edges(self) -> None:
        for task in self.tasks.values():
            for dep in task.depends_on:
                if dep not in self.tasks:
                    raise DagError(
                        f"Task '{task.id}' depends on unknown task '{dep}'.")
                if dep == task.id:
                    raise DagError(f"Task '{task.id}' depends on itself.")

    def _compute_levels(self) -> list[list[str]]:
        """Kahn's algorithm. Raises on cycles. Returns parallelisable levels."""
        indegree = {tid: 0 for tid in self.tasks}
        dependents: dict[str, list[str]] = {tid: [] for tid in self.tasks}
        for t in self.tasks.values():
            for dep in t.depends_on:
                indegree[t.id] += 1
                dependents[dep].append(t.id)

        ready = sorted(tid for tid, d in indegree.items() if d == 0)
        levels: list[list[str]] = []
        seen = 0
        while ready:
            levels.append(ready)
            seen += len(ready)
            nxt: list[str] = []
            for tid in ready:
                for child in dependents[tid]:
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        nxt.append(child)
            ready = sorted(nxt)

        if seen != len(self.tasks):
            stuck = [tid for tid, d in indegree.items() if d > 0]
            raise DagError(f"Cycle detected involving: {sorted(stuck)}")
        return levels

    # ------------------------------------------------------------------ #
    @property
    def levels(self) -> list[list[str]]:
        """Topologically ordered groups; tasks within a group are independent."""
        return self._levels

    def topological_order(self) -> list[str]:
        return [tid for level in self._levels for tid in level]

    def __len__(self) -> int:
        return len(self.tasks)
