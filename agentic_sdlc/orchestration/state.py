"""Workflow-state checkpointing.

The full :class:`WorkflowState` is serialisable, so we snapshot it to disk after
each major phase. If a run crashes or a human pauses it at a gate, it can be
inspected — and the design leaves the door open to resuming from a checkpoint.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import WorkflowState


def save_checkpoint(state: WorkflowState, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"state_{state.run_id}.json"
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_checkpoint(path: str | Path) -> WorkflowState:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return WorkflowState.model_validate(data)
