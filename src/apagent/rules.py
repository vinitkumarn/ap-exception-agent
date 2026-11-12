"""Rule checks. ALL math and policy decisions live here. The LLM never does arithmetic.

Pure functions (price_check, qty_check, duplicate_check) take plain values and are easy
to unit test. check_invoice() gathers data from the data layer and runs them all.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from apagent import policy


def D(x) -> Decimal:
    """Money/qty to Decimal. Goes through str() so 0.1 stays 0.1, never 0.1000000000000000055."""
    return Decimal(str(x))


def money(x: Decimal) -> str:
    return str(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass
class Finding:
    check: str            # "price" | "qty" | "duplicate" | "data"
    result: str           # a root-cause code, or "PASS"
    line_num: int | None = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- price ----------
def price_check(inv_price, po_price, qty_billed, line_num=None) -> Finding:
    inv_price, po_price, qty_billed = D(inv_price), D(po_price), D(qty_billed)
    if po_price <= 0:
        return Finding("data", "INSUFFICIENT_DATA", line_num, {"reason": "PO price is zero or negative"})
    pct = (inv_price - po_price) / po_price
    variance_amt = (inv_price - po_price) * qty_billed
    details = {
        "invoice_unit_price": money(inv_price),
        "po_unit_price": money(po_price),
        "variance_pct": str((pct * 100).quantize(Decimal("0.01"))),
        "tolerance_pct": str(policy.PRICE_TOLERANCE_PCT * 100),
        "variance_amount": money(variance_amt),
    }
    if pct <= policy.PRICE_TOLERANCE_PCT:          # under-billing is never a price hold
        return Finding("price", "PASS", line_num, details)
    if variance_amt <= policy.SMALL_VARIANCE_LIMIT:
        return Finding("price", "SMALL_PRICE_VARIANCE", line_num, details)
    return Finding("price", "PRICE_OVER_TOLERANCE", line_num, details)


# ---------- quantity ----------
def qty_check(qty_billed_total, qty_ordered, qty_received, match_type, line_num=None) -> Finding:
    billed, ordered, received = D(qty_billed_total), D(qty_ordered), D(qty_received)
    details = {"qty_billed_total": str(billed), "qty_ordered": str(ordered),
               "qty_received": str(received), "match_type": match_type}
    if billed > ordered:
        details["over_ordered_by"] = str(billed - ordered)
    if match_type == "3-WAY" and billed > received:
        details["over_received_by"] = str(billed - received)
    if billed > ordered + policy.QTY_ORDERED_TOLERANCE:
        return Finding("qty", "QTY_OVER_ORDERED", line_num, details)
    if match_type == "3-WAY" and billed > received + policy.QTY_RECEIVED_TOLERANCE:
        return Finding("qty", "QTY_OVER_RECEIVED", line_num, details)
    return Finding("qty", "PASS", line_num, details)


# ---------- duplicates ----------
def normalize_invoice_num(num: str) -> str:
    """'INV-001', 'inv 001', 'INV001' -> 'INV1'. Catches the variants that slip past ERP entry checks."""
    s = re.sub(r"[^A-Z0-9]", "", (num or "").upper())
    return re.sub(r"(?<=[A-Z])0+(?=\d)|^0+(?=\d)", "", s)


def duplicate_check(invoice: dict, others: list[dict]) -> Finding:
    """invoice/others: dicts with invoice_id, invoice_num, amount, invoice_date (same supplier already)."""
    norm = normalize_invoice_num(invoice["invoice_num"])
    inv_date = date.fromisoformat(invoice["invoice_date"])
    for o in others:
        if o["invoice_id"] == invoice["invoice_id"]:
            continue
        if normalize_invoice_num(o["invoice_num"]) == norm:
            return Finding("duplicate", "DUPLICATE_EXACT", None,
                           {"matched_invoice_id": o["invoice_id"], "matched_invoice_num": o["invoice_num"],
                            "reason": "same supplier, same invoice number after normalizing"})
    for o in others:
        if o["invoice_id"] == invoice["invoice_id"]:
            continue
        days = abs((date.fromisoformat(o["invoice_date"]) - inv_date).days)
        if D(o["amount"]) == D(invoice["amount"]) and days <= policy.DUP_WINDOW_DAYS:
            return Finding("duplicate", "DUPLICATE_POSSIBLE", None,
                           {"matched_invoice_id": o["invoice_id"], "matched_invoice_num": o["invoice_num"],
                            "amount": money(D(o["amount"])), "days_apart": days,
                            "reason": "same supplier, same amount, different number, within window"})
    return Finding("duplicate", "PASS")


def pick_primary(findings: list[Finding]) -> str:
    results = {f.result for f in findings if f.result != "PASS"}
    for code in policy.PRIORITY:
        if code in results:
            return code
    return "NO_ISSUE"


# ---------- orchestration over the data layer ----------
def check_invoice(dl, invoice_id: str) -> tuple[list[Finding], str]:
    """Run every check for one invoice. Returns (findings, primary_root_cause)."""
    inv = dl.query("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,))
    if not inv:
        f = Finding("data", "INSUFFICIENT_DATA", None, {"reason": f"invoice {invoice_id} not found"})
        return [f], "INSUFFICIENT_DATA"
    inv = inv[0]
    findings: list[Finding] = []

    for line in dl.query("SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY line_num", (invoice_id,)):
        po = dl.query("SELECT * FROM po_lines WHERE po_id = ? AND line_num = ?",
                      (line["po_id"], line["po_line_num"]))
        if not po:
            findings.append(Finding("data", "INSUFFICIENT_DATA", line["line_num"],
                                    {"reason": f"PO {line['po_id']} line {line['po_line_num']} not found"}))
            continue
        po = po[0]
        findings.append(price_check(line["unit_price"], po["unit_price"], line["qty_billed"], line["line_num"]))

        received = dl.query("SELECT qty_received FROM receipts WHERE po_id = ? AND line_num = ?",
                            (line["po_id"], line["po_line_num"]))
        total_received = sum((D(r["qty_received"]) for r in received), Decimal("0"))
        prior = dl.query(
            """SELECT il.qty_billed FROM invoice_lines il JOIN invoices i ON i.invoice_id = il.invoice_id
               WHERE il.po_id = ? AND il.po_line_num = ? AND il.invoice_id <> ? AND i.status <> 'CANCELLED'""",
            (line["po_id"], line["po_line_num"], invoice_id))
        billed_total = D(line["qty_billed"]) + sum((D(p["qty_billed"]) for p in prior), Decimal("0"))
        findings.append(qty_check(billed_total, po["qty_ordered"], total_received, po["match_type"],
                                  line["line_num"]))

    others = dl.query(
        "SELECT invoice_id, invoice_num, amount, invoice_date FROM invoices "
        "WHERE supplier_id = ? AND invoice_id <> ? AND status <> 'CANCELLED'",
        (inv["supplier_id"], invoice_id))
    findings.append(duplicate_check(inv, others))
    return findings, pick_primary(findings)
