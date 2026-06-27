"""FastAPI server — exposes the agentic SDLC pipeline over HTTP with SSE streaming.

Run:
    uvicorn server:app --reload --port 8000

In development the React dev-server (port 5173) proxies /api/* here.
In production point --app-dir to ui/dist and StaticFiles serves the built UI.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agentic_sdlc.config import Settings
from agentic_sdlc.guardrails.input_guard import GuardrailError
from agentic_sdlc.hitl.approval import ApprovalRequired
from agentic_sdlc.logging_config import configure_logging
from agentic_sdlc.orchestration import Orchestrator

app = FastAPI(title="Agentic SDLC Server", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_OUTPUT_DIR = Path("output")


class _SSEHandler(logging.Handler):
    """Forwards log records from the run thread into a queue for SSE streaming."""

    def __init__(self, q: queue.Queue, thread_id: int) -> None:
        super().__init__()
        self.q = q
        self._tid = thread_id

    def emit(self, record: logging.LogRecord) -> None:
        if threading.get_ident() != self._tid:
            return  # ignore logs from other concurrent runs
        self.q.put({
            "type": "log",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        })


@app.post("/api/run")
async def run_pipeline(request: Request):
    body = await request.json()
    requirement: str = body.get("requirement", "").strip()
    mock: bool = bool(body.get("mock", False))
    # API key can arrive in body or header (header takes priority)
    api_key: str | None = (
        request.headers.get("x-api-key") or body.get("api_key") or None
    )

    if not requirement:
        return JSONResponse(status_code=400, content={"error": "requirement is required"})

    log_queue: queue.Queue = queue.Queue()
    tid_holder: list[int] = []   # filled by the thread before logging starts

    def _run() -> None:
        tid_holder.append(threading.get_ident())

        settings = Settings()
        if api_key:
            settings.anthropic_api_key = api_key
        if mock:
            settings.force_mock = True

        configure_logging(settings.log_level, settings.log_json)

        handler = _SSEHandler(log_queue, threading.get_ident())
        handler.setFormatter(logging.Formatter("%(message)s"))
        root = logging.getLogger()
        root.addHandler(handler)

        try:
            orch = Orchestrator(settings=settings)
            state = orch.run(requirement)
            log_queue.put({
                "type": "done",
                "run_id": state.run_id,
                "artifacts": len(state.all_artifacts()),
                "tests_passed": (
                    state.validation.tests_passed if state.validation else None
                ),
            })
        except ApprovalRequired as exc:
            log_queue.put({"type": "halted", "reason": str(exc)})
        except GuardrailError as exc:
            log_queue.put({"type": "error", "msg": str(exc)})
        except Exception as exc:  # noqa: BLE001
            log_queue.put({"type": "error", "msg": str(exc)})
        finally:
            root.removeHandler(handler)
            log_queue.put(None)  # sentinel — stream ends

    threading.Thread(target=_run, daemon=True).start()

    def _stream():
        while True:
            item = log_queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/artifacts")
def list_artifacts():
    if not _OUTPUT_DIR.exists():
        return []
    files = []
    for f in sorted(_OUTPUT_DIR.rglob("*")):
        if f.is_file() and not any(
            skip in f.parts for skip in ("checkpoints", "__pycache__")
        ):
            files.append(str(f.relative_to(_OUTPUT_DIR)).replace("\\", "/"))
    return files


@app.get("/api/artifacts/{path:path}")
def get_artifact(path: str):
    target = (_OUTPUT_DIR / path).resolve()
    if not target.is_relative_to(_OUTPUT_DIR.resolve()):
        return JSONResponse(status_code=403, content={"error": "Forbidden"})
    if not target.exists():
        return JSONResponse(status_code=404, content={"error": "Not found"})
    return {
        "path": path,
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


# Serve the built React app in production (ui/dist must exist)
_UI_DIST = Path("ui/dist")
if _UI_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_UI_DIST), html=True), name="ui")
