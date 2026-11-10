"""A fake 'Claude' for tests: same interface as client.messages.create, scripted answers.

Why: you can test the LOOP (allow-list, step limit, retry, guard, audit) for free, offline, and
deterministically. It is NOT a measure of model quality -- the real eval uses the real model.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

from apagent import policy


def _block_tool(name, args, n):
    return SimpleNamespace(type="tool_use", id=f"toolu_{n}", name=name, input=args)


def _resp(blocks):
    return SimpleNamespace(content=blocks, stop_reason="tool_use",
                           usage=SimpleNamespace(input_tokens=900, output_tokens=120))


class _Messages:
    def __init__(self, outer):
        self.outer = outer

    def create(self, **kw):
        return self.outer._next(kw["messages"])


class ScriptedClient:
    """behavior: good | bad_tool | invalid | loop | wrong"""

    def __init__(self, dl=None, behavior: str = "good"):
        self.behavior = behavior
        self.messages = _Messages(self)
        self.calls = 0

    def _next(self, messages):
        self.calls += 1
        turn = sum(1 for m in messages if m["role"] == "assistant") + 1
        inv = re.search(r"invoice (I\d+)", messages[0]["content"]).group(1)
        b = self.behavior

        if b == "loop":
            return _resp([_block_tool("get_invoice", {"invoice_id": inv}, self.calls)])
        if b == "bad_tool" and turn == 1:
            return _resp([_block_tool("release_hold", {"invoice_id": inv}, self.calls)])
        if b == "bad_tool":
            turn -= 1
        if turn == 1:
            return _resp([_block_tool("get_invoice", {"invoice_id": inv}, self.calls)])
        if turn == 2:
            return _resp([_block_tool("run_checks", {"invoice_id": inv}, self.calls)])
        if b == "invalid":
            return _resp([_block_tool("submit_suggestion", {"invoice_id": inv, "root_cause": "NO_ISSUE"},
                                      self.calls)])
        return _resp([_block_tool("submit_suggestion", self._suggest(inv, messages), self.calls)])

    def _suggest(self, inv, messages):
        findings = []
        for m in messages:
            if m["role"] == "user" and isinstance(m["content"], list):
                for part in m["content"]:
                    if part.get("type") == "tool_result" and '"findings"' in part["content"]:
                        findings = json.loads(part["content"])["findings"]
        failed = {f["result"] for f in findings if f["result"] != "PASS"}
        rc = next((c for c in policy.PRIORITY if c in failed), "NO_ISSUE")
        if self.behavior == "wrong":
            rc = "NO_ISSUE"
        route, step, status = policy.ROUTING[rc]
        ev = [f"{f['check']} line {f['line_num']}: {f['result']}" for f in findings][:6] or ["no findings"]
        return {"invoice_id": inv, "root_cause": rc, "route_to": route, "next_step": step, "status": status,
                "explanation": f"Scripted explanation: rule checks returned {rc}; route to {route}.",
                "evidence": ev,
                "needs_human_reason": "grey area per policy" if status == "NEEDS_HUMAN" else None}
