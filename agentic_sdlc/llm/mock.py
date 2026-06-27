"""Deterministic offline LLM backend.

Returns canned-but-realistic JSON for every pipeline stage so the entire
workflow runs with **no API key**. Three scenarios are recognised from the
requirement text:

* **url shortener** -> the mandatory greenfield use case (emits a real app)
* **rate limit / brownfield** -> a change to an existing codebase
* otherwise / "make it better" -> an ambiguous requirement

For any other text it still returns a valid generic plan so the pipeline never
crashes — it just won't be bespoke. Live mode (a real API key) produces fully
bespoke output for *any* requirement.
"""

from __future__ import annotations

import json

from .fixtures import URL_SHORTENER_FILES


def _scenario(requirement: str) -> str:
    r = requirement.lower()
    # Order matters: the rate-limiting signal is the more specific intent and
    # must win even when the requirement also mentions the URL shortener it
    # modifies ("add rate limiting to the URL shortener").
    if "rate limit" in r or "rate-limit" in r or "throttle" in r:
        return "brownfield_ratelimit"
    if "url shortener" in r or ("shorten" in r and "url" in r):
        return "url_shortener"
    if any(k in r for k in ("make it better", "improve the app", "better and faster",
                            "optimize the app", "enhance")):
        return "ambiguous"
    return "generic"


# --------------------------------------------------------------------------- #
# Fixture builders (return Python objects; serialised to JSON on the way out).
# --------------------------------------------------------------------------- #
def _req_url_shortener() -> dict:
    return {
        "title": "Scalable URL Shortener Service",
        "summary": ("Build a service that turns long URLs into short codes, "
                    "persists the mapping, redirects on lookup, and reports "
                    "click analytics, designed to scale horizontally."),
        "kind": "greenfield",
        "goals": [
            "Create short codes for arbitrary http/https URLs",
            "Redirect short codes to their target",
            "Expose click analytics per code",
            "Persist mappings durably",
        ],
        "non_goals": ["User accounts/auth (out of scope v1)", "Custom domains"],
        "functional_requirements": [
            "POST /api/shorten accepts a URL and optional alias",
            "GET /{code} performs a redirect and records a click",
            "GET /api/stats/{code} returns click totals and recent clicks",
        ],
        "non_functional_requirements": [
            "O(1) code generation, collision-free",
            "Horizontally scalable read path",
            "Input validation to prevent abuse",
        ],
        "ambiguities": [],
        "assumptions": [
            "SQLite is acceptable for the reference build; Postgres in production",
            "307 redirects (temporary) so analytics stay accurate",
        ],
    }


def _decompose_url_shortener() -> dict:
    return {"tasks": [
        {"id": "design-architecture", "title": "Design service architecture",
         "type": "design", "description": "Choose components, storage, code scheme.",
         "depends_on": [], "produces": []},
        {"id": "api-contract", "title": "Define API request/response schemas",
         "type": "schema", "description": "Pydantic contracts for the 3 endpoints.",
         "depends_on": ["design-architecture"], "produces": ["app/schemas.py"]},
        {"id": "persistence", "title": "Implement persistence + code generation",
         "type": "code", "description": "SQLite storage and base62 short codes.",
         "depends_on": ["design-architecture"],
         "produces": ["app/config.py", "app/shortener.py", "app/storage.py"]},
        {"id": "api-endpoints", "title": "Implement FastAPI endpoints",
         "type": "code",
         "description": "Wire schemas + storage into the HTTP layer (join point).",
         "depends_on": ["api-contract", "persistence"],
         "produces": ["app/__init__.py", "app/main.py"]},
        {"id": "tests", "title": "Write integration tests",
         "type": "test", "description": "Exercise shorten/redirect/stats end-to-end.",
         "depends_on": ["api-endpoints"], "produces": ["tests/test_api.py"]},
        {"id": "docs", "title": "Author docs and dependency manifest",
         "type": "docs", "description": "README and requirements.txt.",
         "depends_on": ["api-endpoints"],
         "produces": ["README.md", "requirements.txt"]},
        {"id": "review", "title": "Final review gate",
         "type": "review", "description": "Aggregate risks and validation.",
         "depends_on": ["tests", "docs"], "produces": []},
    ]}


_CODEGEN_URL_SHORTENER = {
    "api-contract": ["app/schemas.py"],
    "persistence": ["app/config.py", "app/shortener.py", "app/storage.py"],
    "api-endpoints": ["app/__init__.py", "app/main.py"],
    "tests": ["tests/test_api.py"],
    "docs": ["README.md", "requirements.txt"],
}


def _codegen(task_id: str, scenario: str) -> dict:
    if scenario == "url_shortener":
        paths = _CODEGEN_URL_SHORTENER.get(task_id, [])
        files = URL_SHORTENER_FILES
    elif scenario == "brownfield_ratelimit":
        paths = _CODEGEN_BROWNFIELD.get(task_id, [])
        files = _BROWNFIELD_FILES
    else:
        paths = []
        files = {}
    return {
        "notes": f"Generated {len(paths)} artifact(s) for task '{task_id}'.",
        "artifacts": [
            {"path": p, "content": files[p], "language":
             "markdown" if p.endswith(".md") or p.endswith(".txt") else "python"}
            for p in paths
        ],
    }


def _validation(scenario: str) -> dict:
    if scenario == "url_shortener":
        return {
            "risks": [
                {"description": "SQLite write contention under high concurrency",
                 "level": "medium",
                 "mitigation": "Move to Postgres; cache reads in Redis."},
                {"description": "Open-redirect / SSRF via attacker-supplied URLs",
                 "level": "medium",
                 "mitigation": "Scheme allow-list enforced; add domain denylist."},
                {"description": "Short-code enumeration leaks link volume",
                 "level": "low",
                 "mitigation": "Randomised id offset; optionally hash-based codes."},
            ],
            "tradeoffs": [
                "SQLite chosen for zero-setup runnability vs. Postgres scalability",
                "Sequential base62 codes are compact but enumerable",
            ],
            "test_strategy": [
                "Integration tests cover shorten/redirect/stats and error paths",
                "Validate scheme rejection and alias conflict (409)",
                "Run pytest in CI; fail the gate on any failure",
            ],
        }
    if scenario == "brownfield_ratelimit":
        return {
            "risks": [
                {"description": "In-memory bucket lost on restart / not shared across pods",
                 "level": "high",
                 "mitigation": "Back the limiter with Redis for multi-instance correctness."},
                {"description": "Legitimate users behind shared NAT throttled together",
                 "level": "medium",
                 "mitigation": "Key on API token where available, fall back to IP."},
            ],
            "tradeoffs": ["Simplicity of in-process limiter vs. distributed accuracy"],
            "test_strategy": ["Unit-test the token bucket refill and rejection at the limit"],
        }
    return {
        "risks": [{"description": "Requirement under-specified; scope may drift",
                   "level": "high",
                   "mitigation": "Resolve ambiguities with stakeholder before build."}],
        "tradeoffs": ["Proceeding on assumptions vs. waiting for clarification"],
        "test_strategy": ["Define acceptance criteria once scope is confirmed"],
    }


def _summary(scenario: str, title: str) -> str:
    return (
        f"This deliverable implements **{title}**. "
        "Implementation proceeded through design -> API contract -> persistence "
        "-> endpoints (join) -> tests + docs -> review. Artifacts were generated "
        "per task and validated by executing the test suite. See the validation "
        "report for risks, trade-offs and the test strategy."
    )


# --------------------------------------------------------------------------- #
# Brownfield fixtures
# --------------------------------------------------------------------------- #
def _req_brownfield() -> dict:
    return {
        "title": "Add per-client rate limiting to the URL shortener",
        "summary": ("Protect the existing shortener API from abuse by limiting "
                    "request rate per client IP, returning HTTP 429 when exceeded."),
        "kind": "brownfield",
        "goals": ["Throttle abusive clients", "Return 429 with Retry-After"],
        "non_goals": ["Per-user quotas (no auth yet)"],
        "functional_requirements": [
            "Reject requests above N per window with 429",
            "Apply globally as ASGI middleware",
        ],
        "non_functional_requirements": ["Low per-request overhead", "Configurable limits"],
        "ambiguities": [],
        "assumptions": ["Single-instance deploy acceptable for v1 (in-memory buckets)"],
    }


def _codebase_brownfield() -> dict:
    return {
        "impacted_components": [
            {"name": "app/main.py", "kind": "module", "change_type": "modify",
             "rationale": "Register the rate-limit middleware on the app."},
            {"name": "app/ratelimit.py", "kind": "module", "change_type": "add",
             "rationale": "New token-bucket limiter implementation."},
            {"name": "app/config.py", "kind": "config", "change_type": "modify",
             "rationale": "Add rate/window settings."},
        ],
        "data_flows": ["Inbound request -> limiter check -> handler or 429"],
        "integration_points": ["FastAPI/Starlette middleware stack"],
        "blast_radius": "medium",
    }


def _decompose_brownfield() -> dict:
    return {"tasks": [
        {"id": "design-architecture", "title": "Design limiter strategy",
         "type": "design", "description": "Token bucket keyed by client IP.",
         "depends_on": [], "produces": []},
        {"id": "implement-ratelimit", "title": "Implement token-bucket limiter",
         "type": "code", "description": "Pure-python limiter + middleware.",
         "depends_on": ["design-architecture"], "produces": ["app/ratelimit.py"]},
        {"id": "tests", "title": "Test limiter behaviour",
         "type": "test", "description": "Refill and rejection at the limit.",
         "depends_on": ["implement-ratelimit"], "produces": ["tests/test_ratelimit.py"]},
        {"id": "review", "title": "Review gate", "type": "review",
         "description": "Aggregate risks.", "depends_on": ["tests"], "produces": []},
    ]}


_BROWNFIELD_FILES = {
    "app/ratelimit.py": '''\
"""In-process token-bucket rate limiter as ASGI middleware.

NOTE: buckets are per-process. For multi-instance deployments back this with a
shared store (e.g. Redis) so limits are enforced cluster-wide.
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class _Bucket:
    __slots__ = ("tokens", "updated")

    def __init__(self, capacity: float) -> None:
        self.tokens = capacity
        self.updated = time.monotonic()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, rate: float = 10.0, per_seconds: float = 1.0,
                 capacity: float | None = None) -> None:
        super().__init__(app)
        self._rate = rate / per_seconds
        self._capacity = capacity if capacity is not None else rate
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(self._capacity))

    def _allow(self, key: str) -> bool:
        b = self._buckets[key]
        now = time.monotonic()
        b.tokens = min(self._capacity, b.tokens + (now - b.updated) * self._rate)
        b.updated = now
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return True
        return False

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "anonymous"
        if not self._allow(client):
            return JSONResponse({"detail": "Too Many Requests"}, status_code=429,
                                headers={"Retry-After": "1"})
        return await call_next(request)
''',
    "tests/test_ratelimit.py": '''\
"""Unit tests for the token-bucket limiter."""

from __future__ import annotations

from app.ratelimit import RateLimitMiddleware


def test_allows_then_blocks():
    mw = RateLimitMiddleware(app=None, rate=2, per_seconds=1, capacity=2)
    assert mw._allow("1.2.3.4") is True
    assert mw._allow("1.2.3.4") is True
    assert mw._allow("1.2.3.4") is False  # bucket exhausted


def test_separate_clients_have_separate_buckets():
    mw = RateLimitMiddleware(app=None, rate=1, per_seconds=1, capacity=1)
    assert mw._allow("a") is True
    assert mw._allow("b") is True
''',
}

_CODEGEN_BROWNFIELD = {
    "implement-ratelimit": ["app/ratelimit.py"],
    "tests": ["tests/test_ratelimit.py"],
}


# --------------------------------------------------------------------------- #
# Ambiguous fixtures
# --------------------------------------------------------------------------- #
def _req_ambiguous() -> dict:
    return {
        "title": "Improve the application",
        "summary": ("The request 'make the app better and faster' lacks a "
                    "measurable target, scope, or definition of 'better'."),
        "kind": "ambiguous",
        "goals": ["Unclear — needs clarification"],
        "non_goals": [],
        "functional_requirements": [],
        "non_functional_requirements": ["'Faster' — no metric or budget given"],
        "ambiguities": [
            {"question": "Which app/component, and what does 'better' mean here?",
             "why_it_matters": "Determines the entire scope of work.",
             "assumed_answer": "Target the URL shortener read path latency."},
            {"question": "What is the performance target (p95 latency, RPS)?",
             "why_it_matters": "Without a target, 'faster' is unverifiable.",
             "assumed_answer": "p95 < 50ms for redirects at 500 RPS."},
            {"question": "Any constraints (budget, no new infra)?",
             "why_it_matters": "Rules some solutions (e.g. Redis) in or out.",
             "assumed_answer": "Prefer no new infra for v1."},
        ],
        "assumptions": [
            "Proceeding with the assumed answers above, pending human approval."
        ],
    }


def _decompose_ambiguous() -> dict:
    return {"tasks": [
        {"id": "clarify", "title": "Document ambiguities and assumptions",
         "type": "design", "description": "Surface open questions for sign-off.",
         "depends_on": [], "produces": []},
        {"id": "proposal", "title": "Draft a scoped improvement proposal",
         "type": "docs", "description": "Concrete plan under stated assumptions.",
         "depends_on": ["clarify"], "produces": []},
        {"id": "review", "title": "Human approval gate", "type": "review",
         "description": "Block until ambiguities are resolved.",
         "depends_on": ["proposal"], "produces": []},
    ]}


def _req_generic(requirement: str) -> dict:
    return {
        "title": requirement[:60] or "Untitled requirement",
        "summary": f"Offline mock interpretation of: {requirement[:200]}",
        "kind": "greenfield",
        "goals": ["Deliver the stated requirement"],
        "non_goals": [], "functional_requirements": [requirement[:200]],
        "non_functional_requirements": [], "ambiguities": [],
        "assumptions": ["Running in offline mock mode; set ANTHROPIC_API_KEY for bespoke output"],
    }


def _decompose_generic() -> dict:
    return {"tasks": [
        {"id": "design-architecture", "title": "Design", "type": "design",
         "description": "Outline the approach.", "depends_on": [], "produces": []},
        {"id": "implement", "title": "Implement", "type": "code",
         "description": "Build it.", "depends_on": ["design-architecture"], "produces": []},
        {"id": "tests", "title": "Test", "type": "test", "description": "Verify.",
         "depends_on": ["implement"], "produces": []},
        {"id": "review", "title": "Review", "type": "review", "description": "Gate.",
         "depends_on": ["tests"], "produces": []},
    ]}


class MockLLMClient:
    """Implements the :class:`LLMClient` protocol with deterministic fixtures."""

    def complete(self, *, system: str, user: str, tag: str,
                 model: str | None = None, max_tokens: int | None = None) -> str:
        scenario = _scenario(user)

        if tag == "requirement":
            payload = {
                "url_shortener": _req_url_shortener,
                "brownfield_ratelimit": _req_brownfield,
                "ambiguous": _req_ambiguous,
            }.get(scenario, lambda: _req_generic(user))()
        elif tag == "codebase":
            payload = _codebase_brownfield() if scenario == "brownfield_ratelimit" else {
                "impacted_components": [], "data_flows": [],
                "integration_points": [], "blast_radius": "low"}
        elif tag == "decompose":
            payload = {
                "url_shortener": _decompose_url_shortener,
                "brownfield_ratelimit": _decompose_brownfield,
                "ambiguous": _decompose_ambiguous,
            }.get(scenario, _decompose_generic)()
        elif tag.startswith("codegen:"):
            payload = _codegen(tag.split(":", 1)[1], scenario)
        elif tag == "validation":
            payload = _validation(scenario)
        elif tag == "summary":
            if "title:" in user:
                # Take only the first line after the "title:" marker so the
                # trailing "summary:" line never leaks into the heading.
                title = user.split("title:", 1)[1].splitlines()[0].strip()[:80]
            else:
                title = "Requirement"
            return _summary(scenario, title)
        else:
            payload = {}

        return json.dumps(payload)
