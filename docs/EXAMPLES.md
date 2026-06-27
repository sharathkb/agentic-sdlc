# Examples: the three scenarios

The assignment asks for three scenarios — a greenfield build, a brownfield
change, and an ambiguous request. All three run offline in mock mode and are
wired into the `Makefile`. The transcripts below are real output (log timestamps
removed for readability).

---

## 1. Greenfield — build the URL shortener

```bash
make run
# or:
python -m agentic_sdlc run --mock \
  "Build a scalable URL shortener service with APIs, persistence, and analytics."
```

What happens:

```
agent.requirement | Classified as greenfield with 0 ambiguities.
agent.decompose   | Produced 7 tasks.
orchestrator | Execution plan has 5 levels:
  [['design-architecture'],
   ['api-contract', 'persistence'],
   ['api-endpoints'],
   ['docs', 'tests'],
   ['review']]
...
agent.validation | Executing generated test suite for verification.
agent.validation | Test execution PASSED.
orchestrator | === Run ... complete ===

Output written to: output/
  - ENGINEERING_SUMMARY.md
  - VALIDATION.md
  - PLAN.json
  - 9 generated artifact(s)
Tests passed: True
```

Things to notice:

* **Parallel levels.** `api-contract` and `persistence` share level 1 and run
  concurrently; `docs` and `tests` share level 3.
* **A real join.** `api-endpoints` sits alone in level 2 because it depends on
  *both* `api-contract` and `persistence` — cross-step coordination, not a line.
* **Empirical validation.** The system runs the generated `tests/test_api.py`
  and reports the actual result, then auto-approves both gates because the
  greenfield build's max risk is only *medium* (below the *high* threshold).

The generated app under `output/` is real and runnable:

```bash
pip install -e ".[app]"
cd output && uvicorn app.main:app --reload

curl -X POST localhost:8000/api/shorten -H 'content-type: application/json' \
     -d '{"url":"https://example.com/a/very/long/path"}'
# {"code":"q0V","short_url":"http://localhost:8000/q0V","long_url":"https://..."}

curl -i localhost:8000/q0V              # 307 redirect to the long URL
curl localhost:8000/api/stats/q0V       # click analytics for that code
```

Security built into the generated service: `http`/`https` scheme allow-list
(`javascript:` and `file:` URLs are rejected with 422), URL/alias length caps,
parameterised SQL, and `307` redirects so analytics stay accurate.

---

## 2. Brownfield — add rate limiting to the existing API

```bash
make run-brownfield
# or:
python -m agentic_sdlc run --mock --file examples/brownfield_add_rate_limiting.md
```

What happens:

```
agent.requirement | Classified as brownfield with 0 ambiguities.
agent.codebase    | Reasoning about codebase impact.
agent.codebase    | Impact: 3 components, blast radius medium.
agent.decompose   | Produced 4 tasks.
orchestrator | Execution plan has 4 levels:
  [['design-architecture'], ['implement-ratelimit'], ['tests'], ['review']]
...
agent.validation | Test execution PASSED.
hitl.approval | Gate 'pre-finalize' requires human approval (risk=high) — halting.
orchestrator | Run halted for human review at final gate.

Run paused for human review: Halted: risk high >= threshold high;
re-run with --interactive to review.
```

Things to notice:

* **A codebase-reasoning phase runs** (it does not for greenfield): the system
  identifies the impacted components and a blast radius before planning.
* **Tests pass, but the run still halts.** Validation flags a *high* risk — an
  in-memory token bucket is correct on one instance but not across pods — so the
  pre-finalize gate stops for a human even though the code is green. This is
  controlled autonomy: passing tests are not sufficient license to ship a
  high-risk change. (Exit code `3`.)

To review and approve as an operator, run it interactively:

```bash
python -m agentic_sdlc run --interactive --mock \
  --file examples/brownfield_add_rate_limiting.md
# === APPROVAL GATE: pre-finalize (risk=high) ===
# Approve? [y/N] y
```

---

## 3. Ambiguous — "make it better and faster"

```bash
make run-ambiguous
# or:
python -m agentic_sdlc run --mock --file examples/ambiguous_make_it_better.md
```

What happens:

```
agent.requirement | Classified as ambiguous with 3 ambiguities.
hitl.approval | Gate 'post-understanding' requires human approval (risk=high) — halting.
orchestrator | (run stops before any code is generated)

Run paused for human review: Halted: risk high >= threshold high;
re-run with --interactive to review.
```

Things to notice:

* **It stops early, on purpose.** An under-specified requirement is treated as
  *high* risk, so the **post-understanding** gate halts the run *before* any
  decomposition or code generation — the system refuses to guess its way into a
  build. (Exit code `3`.)
* **It does not fail silently.** Three concrete ambiguities are surfaced (with
  why each matters and the default the system would otherwise assume), so a
  human has exactly what they need to decide. Running with `--interactive` lets
  an operator approve the assumptions and let the build proceed.

---

## Where the output goes

Every run writes to the output directory (default `output/`, override with
`-o/--output-dir`):

```
output/
  app/ ...                 generated source (greenfield/brownfield)
  tests/ ...               generated tests the system executed
  ENGINEERING_SUMMARY.md   requirement, plan, artifacts, risks, approvals
  VALIDATION.md            risks, trade-offs, test strategy, real test output
  PLAN.json                the task DAG as data
  checkpoints/             per-phase serialised WorkflowState (resumable/inspectable)
```
