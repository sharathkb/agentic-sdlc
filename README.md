# agentic-sdlc

An agentic system that drives a single software **requirement** through a
controlled software-development lifecycle: it *understands* the requirement,
*decomposes* it into a dependency graph of tasks, *reasons about the codebase*
(for changes to existing systems), *orchestrates* a non-linear multi-step
workflow with error recovery, *generates* the engineering output (code, APIs,
tests, docs), *validates* it by actually running the tests, and produces a final
**engineering summary** — all under **controlled autonomy**, pausing at human
approval gates when risk is high.

The mandatory demonstration use case is a **scalable URL shortener service with
APIs, persistence, and analytics**. Running the system on that requirement emits
a real, runnable FastAPI application — so "just run it" produces working software
at two levels: the meta-system *and* the software it generates.

---

## Why it runs with zero setup

The LLM is behind an injectable interface with two backends:

* `AnthropicLLMClient` — the real model (used when an API key is present).
* `MockLLMClient` — deterministic fixtures, no network, no credentials.

With **no API key the system automatically falls back to the mock**, so the
entire pipeline — including the FastAPI app it generates and that app's passing
test suite — runs completely offline. Pass `--mock` to force it explicitly.

---

## Quickstart

```bash
# 1. Install the core system (offline mock mode needs nothing else)
pip install -e .

# 2. Run the mandatory use case (offline, deterministic)
python -m agentic_sdlc run --mock \
  "Build a scalable URL shortener service with APIs, persistence, and analytics."

# 3. Look at what it produced
ls output/
#   app/                  <- a real FastAPI URL shortener
#   tests/test_api.py     <- tests the system ran for you (they pass)
#   ENGINEERING_SUMMARY.md
#   VALIDATION.md
#   PLAN.json
#   checkpoints/
```

To run the **generated** application:

```bash
pip install -e ".[app]"          # fastapi, uvicorn, httpx
cd output && uvicorn app.main:app --reload
# POST http://127.0.0.1:8000/api/shorten   {"url": "https://example.com"}
# GET  http://127.0.0.1:8000/{code}        -> 307 redirect
# GET  http://127.0.0.1:8000/api/stats/{code}
```

### Live mode (optional, uses the real model)

```bash
pip install -e ".[live]"
export ANTHROPIC_API_KEY=sk-ant-...
python -m agentic_sdlc run \
  "Build a scalable URL shortener service with APIs, persistence, and analytics."
```

With a key present the system uses `claude-sonnet-4-6` for most steps and
`claude-opus-4-8` for the hardest reasoning (architecture, decomposition).

---

## The three required scenarios

| Scenario | Command | What it demonstrates |
|---|---|---|
| **Greenfield** | `make run` | Build-from-scratch: full DAG, parallel levels, a real join node, generated app + passing tests. |
| **Brownfield** | `make run-brownfield` | Change to an existing codebase: a codebase-reasoning phase, a **HIGH-risk** finding that **halts for human approval**. |
| **Ambiguous** | `make run-ambiguous` | Under-specified input: three ambiguities surfaced, run **halts at the understanding gate** before any code is written. |

Full walkthroughs with expected output are in [`docs/EXAMPLES.md`](docs/EXAMPLES.md).

---

## Common commands (Makefile)

```
make install         # editable install of the core system
make dev             # install with dev extras (pytest, fastapi, anthropic)
make test            # run the system's own test suite
make run             # greenfield URL shortener (mock)
make run-brownfield  # add rate limiting (mock)
make run-ambiguous   # "make it better and faster" (mock)
make run-app         # start the generated app (after `make run`)
make clean
```

## CLI reference

```
python -m agentic_sdlc run [REQUIREMENT] [options]

  REQUIREMENT          requirement text (or use --file, or pipe via stdin)
  --file, -f PATH      read the requirement from a file
  --output-dir, -o DIR where to write artifacts (default: output/)
  --mock               force the offline deterministic backend
  --interactive        prompt a human at every approval gate
  --log-level LEVEL    DEBUG | INFO | WARNING | ERROR
  --json-logs          emit structured JSON logs (for aggregation)
```

Exit codes: `0` success · `2` input rejected by a guardrail · `3` halted at an
approval gate for human review · `1` unexpected error.

---

## Documentation

* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — design, control flow, the agents, the DAG, and how each assignment requirement is met.
* [`docs/EXAMPLES.md`](docs/EXAMPLES.md) — the three scenarios end to end, with expected output.
* [`docs/TESTING.md`](docs/TESTING.md) — testing approach and how to run the suites.

## Project layout

```
agentic_sdlc/
  models.py            # Pydantic domain model (the typed contract between agents)
  config.py            # settings (env-driven), model selection
  llm/                 # LLM client protocol, Anthropic + mock backends, JSON parsing
  agents/              # one agent per SDLC concern (requirement, codebase, ...)
  orchestration/       # DAG, orchestrator, state/checkpointing, report rendering
  guardrails/          # input sanitisation + output secret scanning
  hitl/                # human-in-the-loop approval gates
  tools/               # sandboxed filesystem + subprocess test runner
  cli.py               # command-line entry point
docs/                  # architecture, examples, testing
examples/              # ready-to-run requirement files
tests/                 # the system's own test suite
```

## Requirements

Python 3.10+. The core system depends only on `pydantic` and
`pydantic-settings`. Optional extras: `live` (the `anthropic` SDK), `app`
(FastAPI/uvicorn/httpx for the generated service), `dev` (pytest + the above).

Licensed under the MIT License.
