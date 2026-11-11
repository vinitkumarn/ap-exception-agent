# Eval report: agent (sqlite)

Cases: 50  |  Exact match (all 4 fields): **100%**

| Field | Accuracy |
|---|---|
| root_cause | 100% |
| route_to | 100% |
| next_step | 100% |
| status | 100% |

| Tag | Exact |
|---|---|
| clean | 10/10 |
| edge | 10/10 |
| exception | 32/32 |
| grey | 9/9 |
| injection | 3/3 |
| pii | 1/1 |

## Agent metrics

- model: claude-sonnet-5-5
- avg_steps: 2.24
- disallowed_tool_calls: 0
- tool_errors: 1
- validation_failures: 1
- guard_overrides: 0
- fallback_to_human: 0
- cases_with_unsupported_numbers: [{'case_id': 'C024', 'numbers': ['40']}]
- injection_cases_passed: 3/3
- avg_input_tokens: 6907
- avg_output_tokens: 704
- cost_per_case_usd: 0.0
- avg_latency_s: 5.3

## Misses

