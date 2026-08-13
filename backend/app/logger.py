"""Append-only JSONL action logger.

Every account operation (create / delete / primary-group change /
secondary-group change) is recorded here as one JSON object per line,
containing every remote command that was run, its stdout/stderr/exit
code, and the overall success/failure of the operation.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "actions.log"

_lock = threading.Lock()


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def write_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Append one structured log entry and return it (with timestamp/id filled in)."""
    _ensure_log_dir()
    entry = dict(entry)
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with _lock:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_entries(limit: int = 100) -> list[dict[str, Any]]:
    """Return the most recent `limit` entries, newest first."""
    _ensure_log_dir()
    if not LOG_FILE.exists():
        return []
    with _lock:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    entries.reverse()
    return entries
