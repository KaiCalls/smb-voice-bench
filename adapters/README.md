# Adapters

> **Disclaimer — not legal or safety advice.** See the repository
> [README](../README.md). These fixtures model behavioral coverage only.

These fixtures are **inert data**. An adapter is a thin mapping from a
`Scenario` into a specific harness's run + judge contract. The fixtures
**complement** these frameworks — they do not replace them. Bring your
framework; bring these fixtures.

Adapters are listed alphabetically and treated as equal peers:

| Adapter | What it is | What's here |
|---------|------------|-------------|
| [`eva/`](eva/) | A horizontal, end-to-end voice-agent evaluation framework (scenario simulation, conversation orchestration, an LLM judge). | Mapping doc + `convert.mjs` converter stub. |
| [`livekit/`](livekit/) | An agents framework that provides test + judge helpers and harness primitives. | Mapping doc + `convert.mjs` converter stub. |

## The shared mapping

Every adapter maps the same four parts of a scenario:

| Scenario part | Maps to |
|---------------|---------|
| `caller_goal` + `script` (caller turns) | the simulated caller / conversation seed |
| `success_criteria` + `failure_traps` + `must_not_claim` + `must_escalate_if` | the judge rubric / expected-behavior assertions |
| `expected_intake_fields` | post-call structured-extraction assertions |
| `severity: critical` | a blocking assertion (fail-closed) |

## Adding an adapter

A new adapter is one peer among equals: a `<name>/README.md` mapping doc and a
`<name>/convert.mjs` converter. Keep it a mapping, not a fork of the schema.
