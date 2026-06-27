"""Code-generation agent.

Invoked once per executable task (code/schema/test/docs). Produces a set of
:class:`Artifact` objects. The stage ``tag`` carries the task id
(``codegen:<task_id>``) so the offline mock can return the right files and so
logs/traces are per-task.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..models import Artifact, NormalizedRequirement, Task
from .base import BaseAgent


class _GeneratedFile(BaseModel):
    path: str
    content: str
    language: str = "python"


class _CodegenResponse(BaseModel):
    notes: str = ""
    artifacts: list[_GeneratedFile] = []


_SYSTEM = """You are a staff engineer writing production-quality code for ONE
task in a larger plan. Write complete, runnable files — no placeholders or TODO
stubs. Follow secure-by-default practices: validate inputs, parameterise SQL,
never hard-code secrets, keep modules small and cohesive. Only produce files
listed in the task's 'produces' (plus closely required helpers).

Respond with ONLY JSON: {"notes": str, "artifacts": [{"path", "content",
"language"}]}. 'path' must be repo-relative (no leading '/' or '..')."""


class CodegenAgent(BaseAgent):
    name = "codegen"

    def run(self, task: Task, requirement: NormalizedRequirement,
            prior_artifacts: list[Artifact]) -> list[Artifact]:
        self.log.info("Generating artifacts for task '%s'.", task.id)
        context_files = "\n".join(f"- {a.path}" for a in prior_artifacts) or "(none)"
        user = (
            f"Requirement: {requirement.title}\n"
            f"Task id: {task.id}\nTask: {task.title}\n"
            f"Description: {task.description}\n"
            f"Expected files (produces): {task.produces}\n"
            f"Files already generated in this run:\n{context_files}"
        )
        resp = self._complete_model(
            system=_SYSTEM, user=user, tag=f"codegen:{task.id}",
            schema=_CodegenResponse)
        artifacts = [
            Artifact(path=f.path, content=f.content, language=f.language,
                     task_id=task.id)
            for f in resp.artifacts
        ]
        self.log.info("Task '%s' produced %d artifact(s).", task.id, len(artifacts))
        return artifacts
