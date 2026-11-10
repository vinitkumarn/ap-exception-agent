"""PII minimization. Two layers:
1. Tools never SELECT sensitive columns (bank_account, tax_id).  <- main control
2. mask() scrubs anything that slips through, e.g. an account number typed into a description.
"""
import re

SENSITIVE_KEYS = {"bank_account", "iban", "tax_id", "routing_number", "swift"}
LONG_DIGITS = re.compile(r"\b\d[\d -]{7,}\d\b")   # long digit runs; masked only if 9+ digits (dates have 8)


def mask_text(text: str) -> str:
    def repl(m):
        digits = re.sub(r"\D", "", m.group())
        return f"****{digits[-4:]}" if len(digits) >= 9 else m.group()
    return LONG_DIGITS.sub(repl, text)


def mask(obj):
    """Recursively mask dicts/lists/strings."""
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if k.lower() in SENSITIVE_KEYS else mask(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask(v) for v in obj]
    if isinstance(obj, str):
        return mask_text(obj)
    return obj
