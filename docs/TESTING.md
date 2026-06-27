# Testing approach

There are **two** layers of tests, and it helps to keep them straight:

1. **The system's own test suite** (`tests/`) — proves the orchestrator,
   guardrails, DAG, and models behave correctly.
2. **The generated app's test suite** (`output/tests/`) — written *by* the
   system for the software it produces, and executed *by* the system during its
   validation phase. You don't run these directly; the pipeline does.

## Running the system's tests

```bash
make dev          # install pytest + the extras the e2e tests need
make test
# or:
pytest -q
```

Expected: **30 passed**. The suite needs `fastapi` and `httpx` installed because
the end-to-end tests let the validation phase actually run the generated app's
tests — they are included in the `dev` extra.

## What the suite covers

| File | Focus |
|---|---|
| `tests/test_models.py` | Pydantic validators and invariants: task-id slugs, artifact path-traversal rejection, `ValidationReport.max_risk`, the `is_ambiguous` rule. |
| `tests/test_dag.py` | The graph engine: linear chains, parallel levels, a **join node** landing after all its parents, and rejection of unknown deps, self-edges, and cycles. |
| `tests/test_guardrails.py` | Input sanitisation (empty/oversized rejected, injection flagged-but-not-blocked) and output secret scanning (keys and private-key blocks caught, clean code passes). |
| `tests/test_orchestrator.py` | Four end-to-end runs in mock mode (see below). |

### The end-to-end orchestrator tests

These run the whole pipeline against the deterministic mock — no network, no
credentials — and assert on the behaviour the assignment cares about:

* **`test_url_shortener_end_to_end`** — greenfield run produces a parallel level,
  all tasks succeed, a runnable `app/main.py` and `tests/test_api.py` are
  generated, validation reports the generated tests **actually passed**, the
  three report files are written, and both gates are recorded.
* **`test_api_endpoints_is_a_join_node`** — asserts `api-endpoints` depends on
  *both* `api-contract` and `persistence` (the cross-step coordination).
* **`test_brownfield_runs_codebase_analysis`** — brownfield run (with simulated
  human approval) performs the codebase-reasoning phase and passes its tests.
* **`test_brownfield_high_risk_halts_without_approval`** — the same change run
  non-interactively **halts** at the final gate because its risk is *high*.
* **`test_ambiguous_halts_at_understanding_gate`** /
  **`test_ambiguous_proceeds_when_approved`** — the ambiguous request halts
  before code generation by default, and proceeds only when a human approves.

Human approval is simulated by monkeypatching `builtins.input` to return `"y"`,
so the interactive path is exercised without a real operator.

## Testing philosophy

* **Deterministic by construction.** The mock backend makes every test
  reproducible and fast (the full suite runs in ~3s) with zero external
  dependencies. The same `LLMClient` seam that enables offline runs is what
  makes the system testable.
* **Validation is empirical.** The e2e tests don't just check that *files* were
  produced — they assert the *generated* test suite was executed and passed.
  The system verifies its own output the same way in production.
* **Negative paths are first-class.** Cycles, unknown dependencies, traversal
  attempts, injected instructions, hard-coded secrets, and high-risk halts all
  have explicit tests. Controlled autonomy is only meaningful if the *stop*
  cases are tested, so they are.

## How the generated tests are run inside the pipeline

During phase 5 the `ValidationAgent` calls `tools/code_runner.run_pytest`, which
executes the generated suite in an **isolated subprocess** with `PYTHONPATH` set
to the workspace so the generated `app` package imports cleanly. The captured
pass/fail result is written into `VALIDATION.md` and feeds the final risk
calculation. A missing test suite is treated as a soft pass — never reported as
a false green.

## Manual smoke test of the generated service

After a greenfield run you can exercise the generated app directly:

```bash
pip install -e ".[app]"
cd output
python -c "
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
r = c.post('/api/shorten', json={'url': 'https://example.com/long/path'})
code = r.json()['code']
assert c.get(f'/{code}', follow_redirects=False).status_code == 307
assert c.get(f'/api/stats/{code}').json()['total_clicks'] == 1
assert c.post('/api/shorten', json={'url': 'javascript:alert(1)'}).status_code == 422
print('generated app OK')
"
```
