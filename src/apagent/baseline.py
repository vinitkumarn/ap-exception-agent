"""Two non-LLM baselines. The agent must be compared against both.

1. rules_only:  run every check in rules.py, route with the policy table. (Best non-AI option.)
2. hold_code:   route purely by the ERP hold code, like a queue rule. (Roughly "today's process".)
"""
from apagent.policy import HOLD_CODE_ROUTING, ROUTING
from apagent.rules import check_invoice

HOLD_ORDER = ["NO PO LINE", "QTY ORD", "QTY REC", "PRICE"]


def rules_only(dl, invoice_id: str) -> dict:
    findings, primary = check_invoice(dl, invoice_id)
    route, step, status = ROUTING[primary]
    return {"root_cause": primary, "route_to": route, "next_step": step, "status": status}


def hold_code(dl, invoice_id: str) -> dict:
    codes = {h["hold_code"] for h in dl.query("SELECT hold_code FROM holds WHERE invoice_id = ?", (invoice_id,))}
    for code in HOLD_ORDER:
        if code in codes:
            rc, route, step, status = HOLD_CODE_ROUTING[code]
            return {"root_cause": rc, "route_to": route, "next_step": step, "status": status}
    return {"root_cause": "NO_ISSUE", "route_to": "NONE", "next_step": "NO_ACTION", "status": "SUGGESTION"}
