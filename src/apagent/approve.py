"""Human approval step (command line). The analyst accepts, rejects or skips each suggestion.

  python -m apagent.approve --approver vinit

Decisions are appended to logs/approvals.jsonl. Nothing is written to the ERP: an approved
suggestion means "the analyst agrees with the reason and next step" -- the analyst still acts in EBS.
"""
import argparse
import json
import time

from apagent.config import ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--approver", required=True)
    ap.add_argument("--file", default=str(ROOT / "reports" / "agent_suggestions.jsonl"))
    a = ap.parse_args()
    log = ROOT / "logs" / "approvals.jsonl"
    log.parent.mkdir(exist_ok=True)

    with open(a.file) as f:
        rows = [json.loads(line) for line in f]
    for r in rows:
        s = r["suggestion"]
        print("\n" + "=" * 70)
        print(f"{r['case_id']}  invoice {s['invoice_id']}  status={s['status']}  confidence={r['confidence']}")
        print(f"Root cause: {s.get('root_cause')}  ->  {s.get('route_to')} / {s.get('next_step')}")
        print(f"Why: {s.get('explanation')}")
        for e in s.get("evidence") or []:
            print(f"  - {e}")
        if s.get("needs_human_reason"):
            print(f"Needs human: {s['needs_human_reason']}")
        choice = ""
        while choice not in {"a", "r", "s", "q"}:
            choice = input("[a]ccept  [r]eject  [s]kip  [q]uit > ").strip().lower()
        if choice == "q":
            break
        if choice == "s":
            continue
        note = input("Note (optional): ").strip()
        with log.open("a") as out:
            out.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "approver": a.approver,
                                  "case_id": r["case_id"], "invoice_id": s["invoice_id"],
                                  "decision": "ACCEPT" if choice == "a" else "REJECT",
                                  "root_cause": s.get("root_cause"), "note": note}) + "\n")
    print(f"\nDecisions saved to {log}")


if __name__ == "__main__":
    main()
