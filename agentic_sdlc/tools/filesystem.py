"""Filesystem confinement.

Every artifact write goes through :class:`SafeWorkspace`, which resolves the
target path and verifies it stays *inside* the workspace root. This blocks the
classic ``../../etc/passwd`` traversal even if a model emits a malicious path
(the Pydantic ``Artifact`` validator is the first line; this is the second).
"""

from __future__ import annotations

import os
from pathlib import Path

from ..models import Artifact


class WorkspaceSecurityError(RuntimeError):
    pass


class SafeWorkspace:
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, rel_path: str) -> Path:
        target = (self.root / rel_path).resolve()
        # is_relative_to (3.9+) uses os.path.normcase internally, so it is
        # case-insensitive on Windows — unlike a raw str.startswith() check.
        if not target.is_relative_to(self.root):
            raise WorkspaceSecurityError(f"Path escapes workspace: {rel_path!r}")
        return target

    def write_artifact(self, artifact: Artifact) -> Path:
        target = self._resolve(artifact.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(artifact.content, encoding="utf-8")
        return target

    def write_text(self, rel_path: str, content: str) -> Path:
        target = self._resolve(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target
