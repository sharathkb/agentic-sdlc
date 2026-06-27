"""Validation by execution.

The validation agent doesn't just *reason* about correctness — it actually runs
the generated test suite in a subprocess and feeds the real pass/fail result
back into the workflow. Running tests out-of-process (rather than importing
generated code into our own interpreter) is a safety boundary: generated code
never executes inside the orchestrator.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_pytest(workdir: str | Path, timeout: int = 120) -> tuple[bool, str]:
    """Run ``pytest`` in ``workdir``. Returns ``(passed, combined_output)``.

    A missing test suite is treated as a soft pass (nothing to fail) but is
    reported in the output so the human gate can see it.
    """
    workdir = Path(workdir)
    tests_dir = workdir / "tests"
    if not tests_dir.exists():
        return True, "No tests/ directory found — skipped execution."

    try:
        env = dict(os.environ)
        # Make the generated package importable from its tests.
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(workdir), env.get("PYTHONPATH", "")])
        )
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return False, "pytest is not installed in this environment."
    except subprocess.TimeoutExpired:
        return False, f"Test run exceeded {timeout}s timeout."

    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output.strip()
