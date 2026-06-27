"""Unit tests for the task dependency graph (levels, joins, cycles)."""

from __future__ import annotations

import pytest

from agentic_sdlc.models import Task, TaskPlan, TaskType
from agentic_sdlc.orchestration.dag import DagError, TaskGraph


def _task(tid: str, deps: list[str] | None = None, ttype: TaskType = TaskType.CODE) -> Task:
    return Task(id=tid, title=tid, type=ttype, description="d", depends_on=deps or [])


def test_levels_linear_chain():
    plan = TaskPlan(tasks=[_task("a"), _task("b", ["a"]), _task("c", ["b"])])
    graph = TaskGraph(plan)
    assert graph.levels == [["a"], ["b"], ["c"]]


def test_levels_parallel_within_level():
    # b and c both depend only on a -> they share a level (can run in parallel).
    plan = TaskPlan(tasks=[_task("a"), _task("b", ["a"]), _task("c", ["a"])])
    graph = TaskGraph(plan)
    assert graph.levels[0] == ["a"]
    assert graph.levels[1] == ["b", "c"]


def test_join_node_waits_for_all_parents():
    # d is a join: depends on BOTH b and c. It must land strictly after them.
    plan = TaskPlan(tasks=[
        _task("a"),
        _task("b", ["a"]),
        _task("c", ["a"]),
        _task("d", ["b", "c"]),
    ])
    graph = TaskGraph(plan)
    order = graph.topological_order()
    assert order.index("d") > order.index("b")
    assert order.index("d") > order.index("c")
    # The join sits alone in the final level.
    assert graph.levels[-1] == ["d"]


def test_unknown_dependency_raises():
    plan = TaskPlan(tasks=[_task("a", ["does-not-exist"])])
    with pytest.raises(DagError):
        TaskGraph(plan)


def test_self_dependency_raises():
    plan = TaskPlan(tasks=[_task("a", ["a"])])
    with pytest.raises(DagError):
        TaskGraph(plan)


def test_cycle_detected():
    plan = TaskPlan(tasks=[_task("a", ["b"]), _task("b", ["a"])])
    with pytest.raises(DagError, match="Cycle"):
        TaskGraph(plan)


def test_topological_order_covers_all_tasks():
    plan = TaskPlan(tasks=[
        _task("a"), _task("b", ["a"]), _task("c", ["a"]), _task("d", ["b", "c"]),
    ])
    graph = TaskGraph(plan)
    assert sorted(graph.topological_order()) == ["a", "b", "c", "d"]
    assert len(graph) == 4
