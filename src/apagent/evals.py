"""Eval: run a mode over every labeled case, score it, write a report.

  python -m apagent.evals --mode rules            # rules-only baseline
  python -m apagent.evals --mode holdcode         # "today's process" baseline
  python -m apagent.evals --mode agent --fake     # agent loop with scripted fake model (no API key)
  python -m apagent.evals --mode agent            # the real thing (needs ANTHROPIC_API_KEY)
  python -m apagent.evals --mode agent --via-mcp  # same, but tools are served over MCP
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from apagent.audit import AuditLog
from apagent.baseline import hold_code, rules_only
from apagent.config import ROOT, get_settings
from apagent.db import get_data_layer
from apagent.schemas import Case

FIELDS = ["root_cause", "route_to", "next_step", "status"]
NUM = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


def load_cases(path: Path | None = None) -> list[Case]:
    path = path or ROOT / "data" / "cases.jsonl"
    with path.open() as f:
        return [Case.model_validate_json(line) for line in f if line.strip()]


def _norm(n: str) -> str:
    n = n.replace(",", "")
    return n.rstrip("0").rstrip(".") if "." in n else n


def unsupported_numbers(text: str, tool_outputs: list[str]) -> list[str]:
    """Numbers the model wrote that appear in NO tool result = possible made-up claims."""
    seen = {_norm(x) for out in tool_outputs for x in NUM.findall(out)}
    return sorted({_norm(x) for x in NUM.findall(text)} - seen)


def score(cases: list[Case], preds: dict[str, dict]) -> dict:
    per_field = {f: 0 for f in FIELDS}
    exact, by_tag, misses = 0, defaultdict(lambda: [0, 0]), []
    for c in cases:
        p = preds[c.case_id]
        ok = {f: p.get(f) == getattr(c.expected, f) for f in FIELDS}
        for f in FIELDS:
            per_field[f] += ok[f]
        exact += all(ok.values())
        for t in c.tags:
            by_tag[t][0] += all(ok.values())
            by_tag[t][1] += 1
        if not all(ok.values()):
            misses.append({"case_id": c.case_id, "tags": c.tags, "note": c.note,
                           "expected": c.expected.root_cause, "got": p.get("root_cause"),
                           "expected_status": c.expected.status, "got_status": p.get("status")})
    n = len(cases)
    return {"n": n, "exact_match": round(exact / n, 3),
            "field_accuracy": {f: round(v / n, 3) for f, v in per_field.items()},
            "by_tag": {t: f"{a}/{b}" for t, (a, b) in sorted(by_tag.items())}, "misses": misses}


def run(mode: str, fake: bool = False, behavior: str = "good", limit: int | None = None,
        via_mcp: bool = False) -> dict:
    s = get_settings()
    dl = get_data_layer(s)
    cases = load_cases()[:limit] if limit else load_cases()
    preds, extra = {}, {}

    if mode in ("rules", "holdcode"):
        fn = rules_only if mode == "rules" else hold_code
        preds = {c.case_id: fn(dl, c.invoice_id) for c in cases}
    elif mode == "agent":
        from apagent.agent import make_client, run_agent
        if fake:
            from apagent.fake_llm import ScriptedClient
            client = ScriptedClient(dl, behavior)
        else:
            client = make_client()
        runner = None
        if via_mcp:
            from apagent.mcp_client import McpToolRunner
            runner = McpToolRunner()
        audit = AuditLog()
        agg = defaultdict(float)
        ungrounded, injection_ok, injection_n = [], 0, 0
        out_path = ROOT / "reports" / "agent_suggestions.jsonl"
        out_path.parent.mkdir(exist_ok=True)
        try:
            with out_path.open("w") as out:
                for c in cases:
                    r = run_agent(c.invoice_id, dl, client, s, audit, tool_runner=runner)
                    preds[c.case_id] = r.suggestion
                    out.write(json.dumps({"case_id": c.case_id, **r.to_dict()}, default=str) + "\n")
                    for k in ["steps", "disallowed_calls", "tool_errors", "validation_failures",
                              "input_tokens", "output_tokens", "latency_s"]:
                        agg[k] += getattr(r, k)
                    agg["guard_overrides"] += r.guard_override
                    agg["fallback_to_human"] += r.suggestion.get("root_cause") is None
                    text = (r.suggestion.get("explanation") or "") + " " + " ".join(r.suggestion.get("evidence") or [])
                    bad = unsupported_numbers(text, r.tool_outputs)
                    if bad:
                        ungrounded.append({"case_id": c.case_id, "numbers": bad})
                    if "injection" in c.tags:
                        injection_n += 1
                        injection_ok += r.suggestion.get("root_cause") == c.expected.root_cause
        finally:
            if runner:
                runner.close()
        n = len(cases)
        cost = (agg["input_tokens"] * s.price_in + agg["output_tokens"] * s.price_out) / 1_000_000
        extra = {
            "model": "scripted-fake" if fake else s.model,
            "avg_steps": round(agg["steps"] / n, 2),
            "disallowed_tool_calls": int(agg["disallowed_calls"]),
            "tool_errors": int(agg["tool_errors"]),
            "validation_failures": int(agg["validation_failures"]),
            "guard_overrides": int(agg["guard_overrides"]),
            "fallback_to_human": int(agg["fallback_to_human"]),
            "cases_with_unsupported_numbers": ungrounded,
            "injection_cases_passed": f"{injection_ok}/{injection_n}",
            "avg_input_tokens": round(agg["input_tokens"] / n),
            "avg_output_tokens": round(agg["output_tokens"] / n),
            "cost_per_case_usd": round(cost / n, 5),
            "avg_latency_s": round(agg["latency_s"] / n, 2),
        }
    else:
        raise ValueError(mode)

    report = {"mode": mode + ("-fake" if fake else "") + ("-mcp" if via_mcp else ""),
              "backend": s.backend, **score(cases, preds), **({"agent": extra} if extra else {})}
    write_report(report)
    return report


def write_report(r: dict):
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / f"report_{r['mode']}.json").write_text(json.dumps(r, indent=2))
    lines = [f"# Eval report: {r['mode']} ({r['backend']})", "",
             f"Cases: {r['n']}  |  Exact match (all 4 fields): **{r['exact_match']:.0%}**", "",
             "| Field | Accuracy |", "|---|---|"]
    lines += [f"| {f} | {v:.0%} |" for f, v in r["field_accuracy"].items()]
    lines += ["", "| Tag | Exact |", "|---|---|"] + [f"| {t} | {v} |" for t, v in r["by_tag"].items()]
    if "agent" in r:
        lines += ["", "## Agent metrics", ""] + [f"- {k}: {v}" for k, v in r["agent"].items()]
    lines += ["", "## Misses", ""] + [
        f"- {m['case_id']} {m['tags']}: expected {m['expected']}/{m['expected_status']}, "
        f"got {m['got']}/{m['got_status']} ({m['note']})" for m in r["misses"]] or ["- none"]
    (out / f"report_{r['mode']}.md").write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["rules", "holdcode", "agent"], required=True)
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--behavior", default="good")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--via-mcp", action="store_true")
    a = ap.parse_args()
    r = run(a.mode, a.fake, a.behavior, a.limit, a.via_mcp)
    print(f"{r['mode']}: exact match {r['exact_match']:.0%} on {r['n']} cases; "
          f"fields {r['field_accuracy']}")
    if "agent" in r:
        print(json.dumps(r["agent"], indent=2))
    print(f"Report: reports/report_{r['mode']}.md")


if __name__ == "__main__":
    main()
