# EVA adapter

> **Disclaimer — not legal or safety advice.** See the repository
> [README](../../README.md).

[ServiceNow EVA](https://github.com/ServiceNow/eva) is a horizontal, end-to-end
voice-agent evaluation framework: it simulates a caller, orchestrates the
conversation with your agent, and grades the result with an LLM judge. It
expects you to bring your agent **and** your scenarios. This adapter supplies the
scenarios.

This is a peer adapter — see the [adapters overview](../README.md). The fixtures
complement EVA; they do not replace it.

## Mapping

| smb-voice-bench `Scenario` | EVA concept |
|----------------------------|-------------|
| `caller_goal` | the simulated user's objective / persona goal |
| `script[]` caller turns | seed turns for the conversation simulation (and any embedded noise/interruption artifacts) |
| `business_context` | the system/world context the agent-under-test is given |
| `success_criteria` | positive expected-behavior assertions in the judge rubric |
| `failure_traps[]` + `must_not_claim` | negative expected-behavior assertions ("must not …") |
| `must_escalate_if` | escalation/redirect assertions |
| `expected_intake_fields[]` | structured-extraction checks on the post-call data |
| `severity: critical` | a blocking assertion: a failure fails the run |

## Converter stub

`convert.mjs` reads the fixtures and emits one EVA-shaped scenario object per
fixture. It is a **starting point** — pin the exact field names to the EVA
version you run.

```bash
# print converted scenarios to stdout
node adapters/eva/convert.mjs

# or write one JSON file per scenario into a directory
node adapters/eva/convert.mjs --out build/eva
```

> The emitted shape is illustrative. Treat the converter as a template you adapt
> to EVA's current scenario format, not a guaranteed-compatible export.
