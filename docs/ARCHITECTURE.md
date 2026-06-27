# Architecture

This document explains how the system is put together, why it is shaped this
way, and where each capability the assignment asks for actually lives in the
code.

## 1. Design goals

The system is a **hand-written multi-agent orchestrator** — deliberately *not*
built on a framework like LangGraph. The assignment is about demonstrating
judgement over the agentic SDLC, so the control flow is explicit and auditable:
you can read `orchestrator.py` top to bottom and see every phase, every gate,
every recovery path. Nothing important happens inside a library you can't see.

Four principles drive the design:

1. **A typed contract between agents.** Every hand-off is a validated Pydantic
   model (`models.py`), not a free-form string. An agent cannot silently emit a
   malformed task list or an unsafe file path — the model rejects it at the
   boundary.
2. **The LLM is an injected dependency.** Agents depend on a small `LLMClient`
   protocol, so the real backend and a deterministic mock are interchangeable.
   This is what makes the whole system runnable offline and testable without
   credentials.
3. **Autonomy is bounded by gates.** The system acts on its own but stops for a
   human at defined points, and the *default* on high risk is to halt rather
   than proceed.
4. **Defence in depth.** Guardrails sit on both the input (untrusted
   requirement text) and the output (generated code), independent of whatever
   the model was prompted to do.

## 2. The pipeline

A single run threads one mutable `WorkflowState` object through six phases. The
state is checkpointed to disk after every phase, so a run is fully inspectable
and resumable.

```
        requirement (untrusted text)
                 │
        ┌────────▼─────────┐
        │ input guardrails │  sanitise, length-cap, flag injection
        └────────┬─────────┘
                 │
   Phase 1  ┌────▼─────────────┐
 understand │ RequirementAgent │  -> NormalizedRequirement (kind, goals, ambiguities)
            └────┬─────────────┘
                 │  (brownfield only)
   Phase 2  ┌────▼───────────┐
  codebase  │ CodebaseAgent  │  -> CodebaseAnalysis (impacted components, blast radius)
            └────┬───────────┘
                 │
        ╔════════▼═══════════╗
        ║  GATE A: post-     ║  ambiguous => HIGH risk => halt for human
        ║  understanding     ║
        ╚════════┬═══════════╝
                 │
   Phase 3  ┌────▼───────────────┐
 decompose  │ DecompositionAgent │  -> TaskPlan -> TaskGraph (validated DAG)
            └────┬───────────────┘
                 │
   Phase 4  ┌────▼──────────────────────────────────┐
  execute   │ Orchestrator._execute_graph           │
            │  • topological *levels* (Kahn)        │
            │  • parallel within a level (threads)  │
            │  • per-task retry w/ backoff          │
            │  • skip descendants of failed tasks   │
            │  CodegenAgent generates artifacts     │
            └────┬──────────────────────────────────┘
                 │
   Phase 5  ┌────▼───────────────┐
  validate  │ ValidationAgent    │  reason about risks  +  RUN the generated pytest
            └────┬───────────────┘
                 │  output guardrails: scan artifacts for secrets
        ╔════════▼═══════════╗
        ║  GATE B: pre-      ║  HIGH risk / test fail / secret / failed task => halt
        ║  finalize          ║
        ╚════════┬═══════════╝
                 │
   Phase 6  ┌────▼───────────┐
 summarise  │ SummaryAgent   │  -> ENGINEERING_SUMMARY.md, VALIDATION.md, PLAN.json
            └────────────────┘
```

## 3. The agents

Each agent owns exactly one SDLC concern and shares a small `BaseAgent` that
handles the model call, JSON extraction, and schema validation. An agent's job
is to turn one typed input into the next typed output.

| Agent | Input | Output | Notes |
|---|---|---|---|
| `RequirementAgent` | raw text | `NormalizedRequirement` | classifies greenfield / brownfield / ambiguous; surfaces ambiguities |
| `CodebaseAgent` | requirement | `CodebaseAnalysis` | brownfield only; impacted components, blast radius |
| `DecompositionAgent` | requirement | `TaskPlan` | tasks **with dependencies** — the DAG edges |
| `CodegenAgent` | one `Task` | `list[Artifact]` | invoked per task; tag `codegen:<task-id>` |
| `ValidationAgent` | requirement + workspace | `ValidationReport` | reasons about risk **and empirically runs the tests** |
| `SummaryAgent` | requirement | narrative markdown | the human-readable rationale |

The "planner" agents (architecture/decomposition) are allowed to request the
heavier model (`claude-opus-4-8`); everything else uses the cheaper worker model
(`claude-sonnet-4-6`).

## 4. Orchestration: why it is not linear

Decomposition produces tasks with `depends_on` edges. `TaskGraph` (in
`orchestration/dag.py`) validates those edges (every dependency exists, no
self-edges), then runs **Kahn's algorithm** to produce *levels*: a topological
grouping where everything in a level is mutually independent and depends only on
earlier levels. Cycles are detected and raised as `DagError`.

For the URL-shortener the levels are:

```
[['design-architecture'],
 ['api-contract', 'persistence'],   <- run in parallel
 ['api-endpoints'],                 <- JOIN: depends on BOTH above
 ['docs', 'tests'],                 <- run in parallel
 ['review']]
```

`api-endpoints` is a genuine **join node** — it waits for *both* `api-contract`
and `persistence` to finish. This is the cross-step coordination the assignment
asks for, and it is what makes the workflow a graph rather than a list. Within a
level, independent tasks run concurrently on a `ThreadPoolExecutor` bounded by
`max_parallelism`.

### Error handling and recovery

* **Per-task retry.** `_execute_task` retries transient failures with
  exponential backoff (`max_retries`, `retry_base_delay`).
* **Containment.** If a task ultimately fails, `_deps_ok` skips the entire
  sub-tree that depended on it instead of crashing the run; siblings still run.
* **Escalation.** Any failed task, a failed test run, a detected secret, or an
  ambiguous requirement escalates the final risk to HIGH, which the final gate
  then acts on.

## 5. Controlled autonomy: the gates

`hitl/approval.py` implements the policy:

* **Interactive mode** — prompt the operator at every gate.
* **Non-interactive mode (default, CI/batch)** — auto-approve *unless* the
  computed risk meets the `approval_required_risk` threshold (default `high`).
  At/above that threshold the gate **hard-stops** the run and records that human
  review is required, rather than silently proceeding. Halting is the
  safety-critical default.

There are two gates: **post-understanding** (catches ambiguous work before any
code is generated) and **pre-finalize** (catches high-risk or failing output
before the run is declared done). Every decision is recorded in the state and
appears in the engineering summary, so the autonomy is auditable after the fact.

## 6. Validation is empirical, not just asserted

The `ValidationAgent` does two things. It reasons about risks, trade-offs, and a
test strategy (the qualitative part), **and** it invokes
`tools/code_runner.run_pytest`, which executes the generated test suite in an
isolated subprocess (its own `PYTHONPATH`, so the generated `app` package
imports cleanly). The real pass/fail result is written into the
`ValidationReport` and feeds the final risk calculation. The system does not
claim its output works — it runs the tests and reports what actually happened.
A missing test suite is treated as a soft pass, never a false green.

## 7. Guardrails and safety

* **Input** (`guardrails/input_guard.py`): rejects empty/oversized requirements
  (cost & abuse control) and flags prompt-injection patterns as warnings routed
  to the human gate. Agent system prompts also treat the requirement strictly as
  data.
* **Output** (`guardrails/output_guard.py`): scans every generated artifact for
  hard-coded secrets (Anthropic/OpenAI/AWS keys, private-key blocks, generic
  `secret = "..."` assignments) before anything is written or shown. A finding
  escalates risk to HIGH.
* **Filesystem** (`tools/filesystem.py`): a `SafeWorkspace` resolves every write
  and confines it under the output root; path traversal raises
  `WorkspaceSecurityError`. The `Artifact` model independently rejects absolute
  paths and `..` segments — defence in depth.
* **Subprocess isolation**: generated tests run in a separate process, not in
  the orchestrator's interpreter.

The **generated** URL shortener carries its own security posture too: an
`http`/`https` scheme allow-list (rejects `javascript:`/`file:` — open-redirect
defence), URL and alias length caps, parameterised SQL throughout, and `307`
redirects so analytics stay accurate.

## 8. How each assignment requirement is met

| Requirement | Where |
|---|---|
| Requirement understanding | `RequirementAgent` -> `NormalizedRequirement` |
| Task decomposition with dependencies | `DecompositionAgent` -> `TaskPlan`; edges validated by `TaskGraph` |
| Codebase reasoning (brownfield) | `CodebaseAgent` -> `CodebaseAnalysis`, runs only for brownfield |
| Non-linear multi-step orchestration | `TaskGraph` levels + join node; `Orchestrator._execute_graph` |
| Cross-step coordination | `api-endpoints` join depends on `api-contract` **and** `persistence` |
| Error handling / recovery | per-task retry + backoff; failed-subtree skipping; risk escalation |
| Engineering output (code/APIs/tests/docs) | `CodegenAgent` -> `Artifact`s -> generated FastAPI app + tests + README |
| Validation & risk control | `ValidationAgent` runs pytest; `ValidationReport.max_risk`; output secret scan |
| Controlled autonomy (act + human approve) | `ApprovalGate`, two gates, halt-on-high-risk default |
| Final engineering summary | `SummaryAgent` + `reporting.render_summary` -> `ENGINEERING_SUMMARY.md` |
| Three scenarios | greenfield / brownfield / ambiguous (see `docs/EXAMPLES.md`) |

## 9. Key files

```
orchestration/orchestrator.py  the six-phase control flow (read this first)
orchestration/dag.py           DAG validation + Kahn levels + cycle detection
orchestration/reporting.py     deterministic markdown report rendering
orchestration/state.py         JSON checkpoint save/load
models.py                      the typed contract between every component
llm/client.py                  LLMClient protocol + Anthropic backend (retry/backoff)
llm/mock.py                    deterministic offline backend + scenario detection
llm/fixtures.py                the real FastAPI app the mock "generates"
agents/base.py                 shared parse/validate plumbing
hitl/approval.py               the approval-gate policy
guardrails/                    input sanitisation + output secret scanning
tools/                         SafeWorkspace + subprocess pytest runner
```

## 10. Web UI and HTTP server

`server.py` wraps the pipeline in an HTTP API with **Server-Sent Events** for
real-time log streaming. The React frontend (`ui/`) communicates with it via a
Vite dev-server proxy.

```
browser (React + Vite, port 5173)
  │  POST /api/run            requirement text + mock flag; x-api-key header
  │  GET  /api/run (SSE)      one JSON event per log line, then a final done/halted event
  │  GET  /api/artifacts      list of paths under output/
  │  GET  /api/artifacts/{p}  raw content of one generated file
  ▼
server.py  (FastAPI, port 8000)
  │  spawns Orchestrator in a background thread
  │  installs a thread-local logging.Handler that converts log records → SSE events
  │  final event: {"type":"done","artifacts":N,"tests_passed":true} or {"type":"halted",...}
  ▼
Orchestrator  (background thread, same process)
```

Security: the Anthropic API key is passed as an `x-api-key` request header and
forwarded to `AnthropicLLMClient`; it is never written to disk server-side.
`localStorage` in the browser is the only persistence for the key.

The Web UI is entirely optional — the core system is a standalone Python package
(`python -m agentic_sdlc run`) with no dependency on Node.js or `server.py`.
The UI layer adds convenience (browser-based input, live log stream, built-in
artifact viewer with syntax highlighting) but does not change any pipeline logic.
