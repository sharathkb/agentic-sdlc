"""Centralised logging.

Supports two modes:

* **human** (default) — colourless, readable, good for local dev.
* **json** — one JSON object per line, ready for log aggregation (Datadog,
  CloudWatch, etc.) in production.

A ``run_id`` is attached to every record via a :class:`logging.LoggerAdapter`
so all lines from one workflow can be correlated.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if run_id := getattr(record, "run_id", None):
            payload["run_id"] = run_id
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO", json_mode: bool = False) -> None:
    handler = logging.StreamHandler(sys.stderr)
    if json_mode:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                              datefmt="%H:%M:%S")
        )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())


def get_logger(name: str, run_id: str | None = None) -> logging.LoggerAdapter:
    base = logging.getLogger(name)
    return logging.LoggerAdapter(base, {"run_id": run_id or "-"})
