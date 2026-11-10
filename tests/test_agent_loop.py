"""The agent loop's safety rails, tested offline with the scripted fake model."""
from apagent.agent import run_agent
from apagent.audit import AuditLog
from apagent.config import get_settings
from apagent.fake_llm import ScriptedClient


def _run(dl, tmp_path, behavior, invoice="I9001"):
    audit = AuditLog(tmp_path / "audit.jsonl")
    return run_agent(invoice, dl, ScriptedClient(dl, behavior), get_settings(), audit), audit


def test_happy_path(dl, tmp_path):
    r, audit = _run(dl, tmp_path, "good")
    assert r.suggestion["root_cause"] == r.rules_primary and r.confidence == "HIGH"
    assert [n for n, _ in r.tool_calls] == ["get_invoice", "run_checks"]
    events = [l for l in audit.path.read_text().splitlines()]
    assert '"case_start"' in events[0] and '"case_end"' in events[-1]


def test_disallowed_tool_is_counted_and_loop_recovers(dl, tmp_path):
    r, _ = _run(dl, tmp_path, "bad_tool")
    assert r.disallowed_calls == 1 and r.suggestion["root_cause"] is not None


def test_invalid_output_retries_once_then_goes_to_human(dl, tmp_path):
    r, _ = _run(dl, tmp_path, "invalid")
    assert r.validation_failures == 2
    assert r.status == "NEEDS_HUMAN" and r.suggestion["needs_human_reason"] == "invalid_output_after_retry"


def test_step_limit_sends_to_human(dl, tmp_path, monkeypatch):
    monkeypatch.setenv("APAGENT_MAX_STEPS", "4")
    r, _ = _run(dl, tmp_path, "loop")
    assert r.steps == 4 and r.status == "NEEDS_HUMAN" and r.confidence == "LOW"


def test_guard_overrides_model_that_disagrees_with_rules(dl, tmp_path, cases):
    price_case = next(c for c in cases if c.expected.root_cause == "PRICE_OVER_TOLERANCE")
    r, _ = _run(dl, tmp_path, "wrong", price_case.invoice_id)   # fake model claims NO_ISSUE
    assert r.guard_override and r.status == "NEEDS_HUMAN"


def test_api_failure_goes_to_human(dl, tmp_path):
    class Broken:
        class messages:
            @staticmethod
            def create(**kw):
                raise ConnectionError("network down")
    r = run_agent("I9001", dl, Broken(), get_settings(), AuditLog(tmp_path / "a.jsonl"))
    assert r.status == "NEEDS_HUMAN" and "model_call_failed" in r.error
