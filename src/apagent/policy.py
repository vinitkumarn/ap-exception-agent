"""Business policy as DATA, not buried in code.

The AP Process Owner owns these numbers. Changing a tolerance should be a
one-line change here, reviewed like any other config change.
"""
from decimal import Decimal

PRICE_TOLERANCE_PCT = Decimal("0.05")    # invoice price may exceed PO price by up to 5%
SMALL_VARIANCE_LIMIT = Decimal("25.00")  # over-tolerance but total variance <= $25 -> grey area
QTY_RECEIVED_TOLERANCE = Decimal("0")    # 3-way: cannot bill more than received
QTY_ORDERED_TOLERANCE = Decimal("0")     # cannot bill more than ordered
DUP_WINDOW_DAYS = 30                     # same supplier + same amount within 30 days -> possible duplicate

# When an invoice has several issues, the most serious one is the "primary" root cause.
# Order = what to fix first. Can't assess > don't pay twice > overbilled > not received > price.
PRIORITY = [
    "INSUFFICIENT_DATA",
    "DUPLICATE_EXACT",
    "DUPLICATE_POSSIBLE",
    "QTY_OVER_ORDERED",
    "QTY_OVER_RECEIVED",
    "PRICE_OVER_TOLERANCE",
    "SMALL_PRICE_VARIANCE",
    "NO_ISSUE",
]

# Root cause -> (route_to, next_step, status). This is the routing table from docs/business_rules.md.
ROUTING = {
    "INSUFFICIENT_DATA":    ("AP",          "INVESTIGATE_MISSING_DATA",   "NEEDS_HUMAN"),
    "DUPLICATE_EXACT":      ("AP",          "REJECT_DUPLICATE",           "SUGGESTION"),
    "DUPLICATE_POSSIBLE":   ("AP",          "REVIEW_POSSIBLE_DUPLICATE",  "NEEDS_HUMAN"),
    "QTY_OVER_ORDERED":     ("AP",          "REQUEST_CORRECTED_INVOICE",  "SUGGESTION"),
    "QTY_OVER_RECEIVED":    ("RECEIVING",   "CONFIRM_RECEIPT",            "SUGGESTION"),
    "PRICE_OVER_TOLERANCE": ("PROCUREMENT", "CONFIRM_PRICE_WITH_BUYER",   "SUGGESTION"),
    "SMALL_PRICE_VARIANCE": ("AP",          "REVIEW_SMALL_VARIANCE",      "NEEDS_HUMAN"),
    "NO_ISSUE":             ("NONE",        "NO_ACTION",                  "SUGGESTION"),
}

# "Today's process" baseline: route purely by the ERP hold code, no investigation.
HOLD_CODE_ROUTING = {
    "PRICE":   ("PRICE_OVER_TOLERANCE", "PROCUREMENT", "CONFIRM_PRICE_WITH_BUYER", "SUGGESTION"),
    "QTY REC": ("QTY_OVER_RECEIVED",    "RECEIVING",   "CONFIRM_RECEIPT",          "SUGGESTION"),
    "QTY ORD": ("QTY_OVER_ORDERED",     "AP",          "REQUEST_CORRECTED_INVOICE", "SUGGESTION"),
    "NO PO LINE": ("INSUFFICIENT_DATA", "AP",          "INVESTIGATE_MISSING_DATA", "NEEDS_HUMAN"),
}
