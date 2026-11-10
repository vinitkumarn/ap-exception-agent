"""JSON-lines audit log: one line per step, append-only. Grep-able, loads into any tool.

We log ids, tool names, arguments, sizes and a hash of each tool result -- not the raw
data -- so the log itself doesn't become a second copy of AP data.
"""
import hashlib
import json
import time
import uuid
from pathlib import Path

from apagent.config import ROOT


class AuditLog:
    def __init__(self, path: Path | None = None, run_id: str | None = None):
        self.path = path or ROOT / "logs" / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or uuid.uuid4().hex[:12]

    def log(self, event: str, **fields):
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_id": self.run_id, "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")

    @staticmethod
    def digest(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]
