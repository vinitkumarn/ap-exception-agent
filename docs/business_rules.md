# Business Rules

All values live in `src/apagent/policy.py`. The **AP Process Owner** owns them.

## Tolerances
| Rule | Value | Notes |
|---|---|---|
| Price tolerance | invoice price ≤ PO price + 5% | Exactly +5% passes. Under-billing never holds. |
| Small-variance band | over tolerance but total variance ≤ $25 | Grey area → human (write-off policy) |
| Qty vs received (3-way) | billed total ≤ received | "Billed total" includes earlier invoices on the PO line |
| Qty vs ordered | billed total ≤ ordered | Applies to 2-way and 3-way |
| Duplicate, exact | same supplier + same invoice number after normalizing | `INV-001` = `inv 001` = `INV001` |
| Duplicate, possible | same supplier + same amount + different number + ≤30 days apart | Grey: could be a recurring fee |

## Priority (when several checks fail)
INSUFFICIENT_DATA → DUPLICATE_EXACT → DUPLICATE_POSSIBLE → QTY_OVER_ORDERED → QTY_OVER_RECEIVED →
PRICE_OVER_TOLERANCE → SMALL_PRICE_VARIANCE → NO_ISSUE.
Reason: can't assess > don't pay twice > overbilled > not yet received > price.

## Routing
| Root cause | Route to | Next step | Status | Who decides grey areas |
|---|---|---|---|---|
| INSUFFICIENT_DATA | AP | INVESTIGATE_MISSING_DATA | NEEDS_HUMAN | AP |
| DUPLICATE_EXACT | AP | REJECT_DUPLICATE | SUGGESTION | AP |
| DUPLICATE_POSSIBLE | AP | REVIEW_POSSIBLE_DUPLICATE | NEEDS_HUMAN | AP (with Procurement for contracts) |
| QTY_OVER_ORDERED | AP | REQUEST_CORRECTED_INVOICE | SUGGESTION | AP |
| QTY_OVER_RECEIVED | RECEIVING | CONFIRM_RECEIPT | SUGGESTION | Receiving |
| PRICE_OVER_TOLERANCE | PROCUREMENT | CONFIRM_PRICE_WITH_BUYER | SUGGESTION | Procurement (buyer) |
| SMALL_PRICE_VARIANCE | AP | REVIEW_SMALL_VARIANCE | NEEDS_HUMAN | AP Process Owner + Accounting |
| NO_ISSUE | NONE | NO_ACTION | SUGGESTION | n/a |
