"""Real, runnable source for the URL-shortener reference app.

These strings are what the code-generation agent "produces" when running in
mock (offline) mode for the mandatory use case. They are deliberately a
complete, working FastAPI service — not pseudocode — so that ``just run it``
yields software you can actually start and exercise.

Security choices baked in:
* URL scheme allow-list (http/https only) to blunt ``javascript:``/``file:`` abuse.
* Length caps on URLs and aliases (DoS / storage abuse).
* Parameterised SQL everywhere (no string interpolation -> no SQLi).
* Custom-alias charset allow-list.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
URL_SHORTENER_FILES: dict[str, str] = {}

URL_SHORTENER_FILES["app/__init__.py"] = '"""Scalable URL shortener service."""\n'

URL_SHORTENER_FILES["app/config.py"] = '''\
"""Configuration for the URL shortener (env-driven)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SHORTENER_", extra="ignore")

    db_path: str = "shortener.db"
    # Public base used to build returned short URLs.
    base_url: str = "http://localhost:8000"
    # Hard limits to prevent storage/DoS abuse.
    max_url_length: int = 2048
    max_alias_length: int = 32
    # Base id offset so the very first code isn't a single character.
    id_offset: int = 100_000


settings = Settings()
'''

URL_SHORTENER_FILES["app/shortener.py"] = '''\
"""Short-code encoding and alias validation."""

from __future__ import annotations

import re

_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE = len(_ALPHABET)
_ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def encode(n: int) -> str:
    """Encode a non-negative integer into a base62 short code."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return _ALPHABET[0]
    out: list[str] = []
    while n:
        n, rem = divmod(n, _BASE)
        out.append(_ALPHABET[rem])
    return "".join(reversed(out))


def decode(code: str) -> int:
    """Inverse of :func:`encode` (handy for tests and debugging)."""
    n = 0
    for ch in code:
        n = n * _BASE + _ALPHABET.index(ch)
    return n


def is_valid_alias(alias: str, max_length: int) -> bool:
    return bool(alias) and len(alias) <= max_length and _ALIAS_RE.match(alias) is not None
'''

URL_SHORTENER_FILES["app/schemas.py"] = '''\
"""Request/response API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ShortenRequest(BaseModel):
    # Provide a concrete example so Swagger UI does not pre-fill the alias
    # field with the placeholder string "string", which causes a 409 on the
    # second attempt when that alias is already taken.
    model_config = ConfigDict(
        json_schema_extra={"example": {"url": "https://example.com/my-long-url"}}
    )

    url: HttpUrl
    alias: Optional[str] = Field(
        default=None, description="Optional custom short code (a-z, A-Z, 0-9, _, -)."
    )


class ShortenResponse(BaseModel):
    code: str
    short_url: str
    long_url: str


class ClickInfo(BaseModel):
    ts: datetime
    referrer: Optional[str] = None
    user_agent: Optional[str] = None


class StatsResponse(BaseModel):
    code: str
    long_url: str
    total_clicks: int
    created_at: datetime
    recent_clicks: list[ClickInfo]
'''

URL_SHORTENER_FILES["app/storage.py"] = '''\
"""SQLite persistence layer (parameterised SQL, thread-safe access)."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT UNIQUE,
    long_url   TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clicks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL,
    ts         TEXT NOT NULL,
    referrer   TEXT,
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks(code);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    """Minimal data-access object. One connection guarded by a lock."""

    def __init__(self, db_path: str, id_offset: int = 100_000) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._id_offset = id_offset
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- writes ------------------------------------------------------------
    def create_link(self, long_url: str, code: Optional[str]) -> str:
        from .shortener import encode

        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO links (code, long_url, created_at) VALUES (?, ?, ?)",
                (code, long_url, _now()),
            )
            row_id = cur.lastrowid
            if code is None:  # auto-generate from the row id
                code = encode(row_id + self._id_offset)
                self._conn.execute(
                    "UPDATE links SET code = ? WHERE id = ?", (code, row_id)
                )
            self._conn.commit()
            return code

    def record_click(self, code: str, referrer: Optional[str],
                     user_agent: Optional[str]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO clicks (code, ts, referrer, user_agent) VALUES (?,?,?,?)",
                (code, _now(), referrer, user_agent),
            )
            self._conn.commit()

    # -- reads -------------------------------------------------------------
    def alias_exists(self, code: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM links WHERE code = ?", (code,)
            ).fetchone()
        return row is not None

    def resolve(self, code: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT long_url FROM links WHERE code = ?", (code,)
            ).fetchone()
        return row["long_url"] if row else None

    def stats(self, code: str, recent: int = 10) -> Optional[dict]:
        with self._lock:
            link = self._conn.execute(
                "SELECT long_url, created_at FROM links WHERE code = ?", (code,)
            ).fetchone()
            if link is None:
                return None
            total = self._conn.execute(
                "SELECT COUNT(*) AS c FROM clicks WHERE code = ?", (code,)
            ).fetchone()["c"]
            rows = self._conn.execute(
                "SELECT ts, referrer, user_agent FROM clicks WHERE code = ? "
                "ORDER BY id DESC LIMIT ?",
                (code, recent),
            ).fetchall()
        return {
            "long_url": link["long_url"],
            "created_at": link["created_at"],
            "total_clicks": total,
            "recent_clicks": [dict(r) for r in rows],
        }

    def close(self) -> None:
        self._conn.close()
'''

URL_SHORTENER_FILES["app/main.py"] = '''\
"""FastAPI application wiring the shortener together."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from .config import settings
from .schemas import ShortenRequest, ShortenResponse, StatsResponse
from .shortener import is_valid_alias
from .storage import Storage

_ALLOWED_SCHEMES = {"http", "https"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.storage = Storage(settings.db_path, settings.id_offset)
    yield
    app.state.storage.close()


app = FastAPI(title="URL Shortener", version="1.0.0", lifespan=lifespan)


def _store(request: Request) -> Storage:
    # The lifespan handler sets this on startup. Fall back to lazy init so the
    # app is robust even if mounted without lifespan (e.g. embedded in tests or
    # another ASGI app) instead of returning an opaque 500.
    state = request.app.state
    if not hasattr(state, "storage"):
        state.storage = Storage(settings.db_path, settings.id_offset)
    return state.storage


# Specific routes first so they are never shadowed by the wildcard /{code}.

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post(
    "/api/shorten",
    response_model=ShortenResponse,
    status_code=201,
    responses={409: {"description": "Alias already taken"}},
)
def shorten(req: ShortenRequest, request: Request) -> ShortenResponse:
    url = str(req.url)
    if len(url) > settings.max_url_length:
        raise HTTPException(status_code=422, detail="URL too long")
    if req.url.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(status_code=422, detail="Only http/https URLs allowed")

    store = _store(request)
    code = None
    if req.alias is not None:
        if not is_valid_alias(req.alias, settings.max_alias_length):
            raise HTTPException(status_code=422, detail="Invalid alias")
        if store.alias_exists(req.alias):
            raise HTTPException(status_code=409, detail="Alias already taken")
        code = req.alias

    code = store.create_link(url, code)
    base = str(request.base_url).rstrip("/")
    return ShortenResponse(
        code=code, short_url=f"{base}/{code}", long_url=url
    )


@app.get("/api/stats/{code}", response_model=StatsResponse)
def stats(code: str, request: Request) -> StatsResponse:
    data = _store(request).stats(code)
    if data is None:
        raise HTTPException(status_code=404, detail="Unknown short code")
    return StatsResponse(code=code, **data)


# Wildcard redirect last — must not shadow any specific route above.
@app.get("/{code}")
def redirect(code: str, request: Request) -> RedirectResponse:
    store = _store(request)
    long_url = store.resolve(code)
    if long_url is None:
        raise HTTPException(status_code=404, detail="Unknown short code")
    store.record_click(
        code,
        referrer=request.headers.get("referer"),
        user_agent=request.headers.get("user-agent"),
    )
    return RedirectResponse(url=long_url, status_code=307)
'''

URL_SHORTENER_FILES["tests/test_api.py"] = '''\
"""Integration tests for the URL shortener API."""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("SHORTENER_DB_PATH", os.path.join(tmp, "test.db"))
    # Import after env is set so Settings picks up the temp DB.
    import importlib
    from app import config, main
    importlib.reload(config)
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_shorten_and_redirect(client):
    r = client.post("/api/shorten", json={"url": "https://example.com/page"})
    assert r.status_code == 201
    code = r.json()["code"]

    redirect = client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "https://example.com/page"


def test_custom_alias_and_conflict(client):
    r = client.post("/api/shorten", json={"url": "https://a.com", "alias": "mylink"})
    assert r.status_code == 201 and r.json()["code"] == "mylink"
    dup = client.post("/api/shorten", json={"url": "https://b.com", "alias": "mylink"})
    assert dup.status_code == 409


def test_rejects_non_http_scheme(client):
    r = client.post("/api/shorten", json={"url": "ftp://example.com"})
    assert r.status_code == 422


def test_stats_counts_clicks(client):
    code = client.post("/api/shorten", json={"url": "https://x.com"}).json()["code"]
    for _ in range(3):
        client.get(f"/{code}", follow_redirects=False)
    stats = client.get(f"/api/stats/{code}").json()
    assert stats["total_clicks"] == 3


def test_unknown_code_404(client):
    assert client.get("/api/stats/nope").status_code == 404
'''

URL_SHORTENER_FILES["requirements.txt"] = '''\
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.6
pydantic-settings>=2.2
httpx>=0.27
pytest>=8.0
'''

URL_SHORTENER_FILES["README.md"] = '''\
# URL Shortener

Scalable URL shortener with REST APIs, SQLite persistence and click analytics.

## Run
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API
| Method | Path                | Purpose                         |
|--------|---------------------|---------------------------------|
| POST   | `/api/shorten`      | Create a short link             |
| GET    | `/{code}`           | Redirect (307) and log a click  |
| GET    | `/api/stats/{code}` | Click analytics for a code      |
| GET    | `/healthz`          | Liveness probe                  |

```bash
curl -X POST localhost:8000/api/shorten -H 'content-type: application/json' \\
  -d '{"url": "https://example.com"}'
```

## Test
```bash
pytest -q
```

## Scaling notes
Swap the SQLite `Storage` for Postgres + a Redis cache on the read path; the
data-access interface is isolated so callers don't change. Short codes are
base62 of a monotonic id, so generation is O(1) and collision-free.
'''
