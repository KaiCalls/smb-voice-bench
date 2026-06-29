# LiveKit adapter

> **Disclaimer — not legal or safety advice.** See the repository
> [README](../../README.md).

[LiveKit Agents](https://github.com/livekit/agents) provides test and judge
helpers plus harness primitives (`agents.test`, mock LLM/STT/TTS, judge helpers)
for agents built on its stack. This adapter maps the fixtures onto that test +
judge shape so the same scenarios grade a LiveKit session.

This is a peer adapter — see the [adapters overview](../README.md). The fixtures
complement LiveKit; they do not replace it.

## Mapping

| smb-voice-bench `Scenario` | LiveKit concept |
|----------------------------|-----------------|
| `script[]` caller turns | the inputs you drive into a test session (one user turn at a time) |
| `business_context` + `caller_goal` | the context you initialize the agent / session with |
| `success_criteria` | judge assertions the final agent turn must satisfy |
| `failure_traps[]` + `must_not_claim` | judge assertions the final agent turn must NOT satisfy |
| `must_escalate_if` | escalation assertions on the judged turn |
| `expected_intake_fields[]` | post-session extraction assertions on captured data |
| `severity: critical` | mark the test as blocking |

## Converter stub

`convert.mjs` reads the fixtures and emits one illustrative LiveKit-style test
spec per fixture (turns to drive + assertions). It is a **starting point** —
adapt the emitted shape to the `agents.test` + judge API version you run.

```bash
# print converted specs to stdout
node adapters/livekit/convert.mjs

# or write one JSON file per scenario into a directory
node adapters/livekit/convert.mjs --out build/livekit
```

A real integration would translate each emitted spec into a LiveKit test case
(drive the `turns`, then run the `judge_assertions` and `extraction_assertions`
against the session). The converter does not depend on LiveKit; it only shapes
the data.
