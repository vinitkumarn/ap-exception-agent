"""The eval itself needs tests: labels, scorer and grounding check."""
from collections import Counter

from apagent.baseline import hold_code, rules_only
from apagent.evals import score, unsupported_numbers


def test_case_set_shape(cases):
    assert len(cases) == 50
    tags = Counter(t for c in cases for t in c.tags)
    assert tags["clean"] >= 10 and tags["grey"] >= 5 and tags["injection"] >= 3
    assert len({c.invoice_id for c in cases}) == 50          # no case reuses an invoice


def test_rules_baseline_agrees_with_seeded_labels(dl, cases):
    """Labels come from the generator plan; rules come from rules.py. They must agree.
    If this fails, either the rule or the label is wrong -- investigate, don't just 'fix the test'."""
    preds = {c.case_id: rules_only(dl, c.invoice_id) for c in cases}
    assert score(cases, preds)["exact_match"] == 1.0


def test_holdcode_baseline_misses_duplicates(dl, cases):
    dups = [c for c in cases if c.expected.root_cause.startswith("DUPLICATE")]
    assert all(hold_code(dl, c.invoice_id)["root_cause"] != c.expected.root_cause for c in dups)


def test_unsupported_numbers():
    tool_out = ['{"po_unit_price": "100.00", "invoice_unit_price": "110.00", "variance_pct": "10.00"}']
    assert unsupported_numbers("Price 110.00 vs 100 is 10% over", tool_out) == []
    assert unsupported_numbers("Price is 12% over on $1,500", tool_out) == ["12", "1500"]
