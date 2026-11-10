"""Unit tests for the pure rule functions. Each test = one business rule, in plain numbers."""
from decimal import Decimal

import pytest

from apagent.rules import D, duplicate_check, normalize_invoice_num, pick_primary, price_check, qty_check, Finding


@pytest.mark.parametrize("inv,po,qty,expected", [
    ("100.00", "100.00", 10, "PASS"),                  # same price
    ("105.00", "100.00", 10, "PASS"),                  # exactly +5% is inside tolerance
    ("105.01", "100.00", 10, "PRICE_OVER_TOLERANCE"),  # one cent over -> hold ($50.10 variance)
    ("90.00", "100.00", 10, "PASS"),                   # under-billing is never a price hold
    ("108.00", "100.00", 2, "SMALL_PRICE_VARIANCE"),   # +8% but only $16 total -> grey area
    ("112.50", "100.00", 2, "SMALL_PRICE_VARIANCE"),   # exactly $25.00 variance -> still grey
    ("112.51", "100.00", 2, "PRICE_OVER_TOLERANCE"),   # $25.02 -> real hold
])
def test_price_check(inv, po, qty, expected):
    assert price_check(inv, po, qty).result == expected


def test_price_check_zero_po_price_is_insufficient_data():
    assert price_check("10", "0", 1).result == "INSUFFICIENT_DATA"


def test_decimal_not_float():
    assert 0.1 + 0.2 != 0.3                        # the float trap
    assert D(0.1) + D(0.2) == Decimal("0.3")       # why every amount goes through D()


@pytest.mark.parametrize("billed,ordered,received,match,expected", [
    (100, 100, 100, "3-WAY", "PASS"),
    (100, 100, 60, "3-WAY", "QTY_OVER_RECEIVED"),
    (120, 100, 100, "3-WAY", "QTY_OVER_ORDERED"),
    (100, 100, 0, "2-WAY", "PASS"),                # 2-way ignores receipts
    (101, 100, 0, "2-WAY", "QTY_OVER_ORDERED"),
])
def test_qty_check(billed, ordered, received, match, expected):
    assert qty_check(billed, ordered, received, match).result == expected


@pytest.mark.parametrize("a,b", [("INV-001", "inv001"), ("INV-70001", "INV.70001"),
                                 ("INV-70001", "INV-070001"), ("00123", "123")])
def test_normalize_same(a, b):
    assert normalize_invoice_num(a) == normalize_invoice_num(b)


def test_normalize_keeps_real_differences():
    assert normalize_invoice_num("INV-1001") != normalize_invoice_num("INV-1010")


def _inv(i, num, amt, d):
    return {"invoice_id": i, "invoice_num": num, "amount": amt, "invoice_date": d}


def test_duplicate_exact_beats_possible():
    me = _inv("I1", "INV-500", "100.00", "2026-10-10")
    others = [_inv("I2", "X-9", "100.00", "2026-10-09"), _inv("I3", "inv 500", "75.00", "2026-09-01")]
    assert duplicate_check(me, others).result == "DUPLICATE_EXACT"


def test_duplicate_possible_window():
    me = _inv("I1", "A1", "100.00", "2026-10-31")
    assert duplicate_check(me, [_inv("I2", "B2", "100.00", "2026-10-01")]).result == "DUPLICATE_POSSIBLE"  # 30 days
    assert duplicate_check(me, [_inv("I2", "B2", "100.00", "2026-09-30")]).result == "PASS"                # 31 days


def test_duplicate_ignores_itself():
    me = _inv("I1", "A1", "100.00", "2026-10-31")
    assert duplicate_check(me, [me]).result == "PASS"


def test_priority_duplicate_wins():
    fs = [Finding("price", "PRICE_OVER_TOLERANCE"), Finding("qty", "QTY_OVER_ORDERED"),
          Finding("duplicate", "DUPLICATE_EXACT")]
    assert pick_primary(fs) == "DUPLICATE_EXACT"
    assert pick_primary([Finding("price", "PASS")]) == "NO_ISSUE"
