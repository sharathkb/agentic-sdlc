"""Command-line interface.

Examples
--------
    # Mandatory use case, fully offline (no API key needed):
    python -m agentic_sdlc run "Build a scalable URL shortener service with \\
        APIs, persistence, and analytics."

    # From a file, interactive approval gates, custom output dir:
    python -m agentic_sdlc run --file examples/greenfield_url_shortener.md \\
        --interactive --output-dir ./out

    # Force live mode (needs ANTHROPIC_API_KEY):
    ANTHROPIC_API_KEY=sk-ant-... python -m agentic_sdlc run "<requirement>"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import get_settings
from .guardrails.input_guard import GuardrailError
from .hitl.approval import ApprovalRequired
from .logging_config import configure_logging
from .orchestration import Orchestrator


def _read_requirement(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.requirement:
        return args.requirement
    return sys.stdin.read()


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentic_sdlc",
                                description="Agentic SDLC workflow runner.")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the full workflow on a requirement.")
    run.add_argument("requirement", nargs="?", help="Requirement text.")
    run.add_argument("--file", "-f", help="Read the requirement from a file.")
    run.add_argument("--output-dir", "-o", help="Where to write artifacts.")
    run.add_argument("--interactive", action="store_true",
                     help="Prompt for approval at each gate.")
    run.add_argument("--mock", action="store_true",
                     help="Force the deterministic offline backend.")
    run.add_argument("--log-level", default=None, help="DEBUG|INFO|WARNING|ERROR")
    run.add_argument("--json-logs", action="store_true", help="Emit JSON logs.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = get_settings()

    # CLI flags override env/.env settings.
    if args.output_dir:
        settings.output_dir = args.output_dir
    if args.interactive:
        settings.interactive = True
    if args.mock:
        settings.force_mock = True
    if args.log_level:
        settings.log_level = args.log_level
    if args.json_logs:
        settings.log_json = True

    configure_logging(settings.log_level, settings.log_json)

    try:
        raw = _read_requirement(args)
        orch = Orchestrator(settings=settings)
        state = orch.run(raw)
    except GuardrailError as exc:
        print(f"Input rejected by guardrail: {exc}", file=sys.stderr)
        return 2
    except ApprovalRequired as exc:
        print(f"\nRun paused for human review: {exc}", file=sys.stderr)
        print(f"Inspect artifacts in: {settings.output_dir}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1

    print("\n" + "=" * 60)
    print(f"Run {state.run_id} complete.")
    print(f"Output written to: {settings.output_dir}/")
    print(f"  - ENGINEERING_SUMMARY.md")
    print(f"  - VALIDATION.md")
    print(f"  - PLAN.json")
    print(f"  - {len(state.all_artifacts())} generated artifact(s)")
    if state.validation:
        print(f"Tests passed: {state.validation.tests_passed}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
