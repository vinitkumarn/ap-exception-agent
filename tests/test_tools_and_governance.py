"""Tools are read-only, validated, masked. Governance controls are tested like features."""
import json

from apagent import tools
from apagent.masking import mask, mask_text


def test_no_write_tools_exist():
    banned = ("release", "update", "delete", "approve", "pay", "insert", "write", "cancel")
    assert not [t for t in tools.ALLOWED_TOOLS if any(b in t for b in banned)]


def test_disallowed_tool_is_refused(dl):
    ok, msg = tools.dispatch(dl, "release_hold", {"invoice_id": "I9001"})
    assert not ok and "not allowed" in msg


def test_bad_arguments_are_refused_before_sql(dl):
    ok, msg = tools.dispatch(dl, "get_invoice", {"invoice_id": "I9001' OR '1'='1"})
    assert not ok and "Invalid arguments" in msg


def test_unknown_invoice_returns_error_text(dl):
    ok, msg = tools.dispatch(dl, "get_invoice", {"invoice_id": "I0000"})
    assert not ok and "not found" in msg


def test_no_bank_or_tax_data_in_any_tool_output(dl, built):
    secrets = [r[3] for r in built.rows["suppliers"]] + [r[4] for r in built.rows["suppliers"]]
    for inv in [r[0] for r in built.rows["invoices"]]:
        for name in ("get_invoice", "find_similar_invoices", "run_checks"):
            ok, out = tools.dispatch(dl, name, {"invoice_id": inv})
            assert not any(s in out for s in secrets), (name, inv)


def test_account_number_in_supplier_text_is_masked(dl, cases):
    pii_case = next(c for c in cases if "pii" in c.tags)
    ok, out = tools.dispatch(dl, "get_invoice", {"invoice_id": pii_case.invoice_id})
    assert ok and "998877665544" not in out and "****5544" in out


def test_supplier_text_is_labeled_untrusted(dl):
    ok, out = tools.dispatch(dl, "get_invoice", {"invoice_id": "I9001"})
    assert "supplier_text_UNTRUSTED" in json.loads(out)


def test_mask_helpers():
    assert mask({"bank_account": "123", "x": {"tax_id": "9"}}) == {"bank_account": "[REDACTED]",
                                                                  "x": {"tax_id": "[REDACTED]"}}
    assert mask_text("date 2026-10-01") == "date 2026-10-01"        # dates survive
    assert mask_text("acct 021000021 5551234") == "acct ****1234"


def test_run_checks_does_not_leak_the_answer(dl):
    ok, out = tools.dispatch(dl, "run_checks", {"invoice_id": "I9001"})
    assert "route_to" not in out and "next_step" not in out
