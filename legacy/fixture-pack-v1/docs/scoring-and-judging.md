# Scoring and judging

> **Disclaimer — not legal or safety advice.** These scenarios model behavioral
> coverage only; see the repository [README](../README.md).

## The aggregation contract

- A judged turn **passes** iff the judge returns `pass`.
- A scenario **passes** iff **every** judged turn passes.
- A suite reports a **pass-rate** (`passed / total`).
- A failing `critical` scenario is **blocking**: surface it separately and
  fail-closed. The reference runner returns these in `blockingFailed`.

This matches how a real grading harness aggregates: positive criteria and
negative traps are both checked, and safety scenarios gate the whole run.

## Bring your own judge

The benchmark ships the judge **contract**, not a graded model, so results stay
runner-agnostic. `runner/judge.mjs` exposes `makeLLMJudge(complete)`: it renders
a scenario's `success_criteria`, `failure_traps`, `must_not_claim`, and
`must_escalate_if` into a single prompt and asks your model to emit exactly
`pass` or `fail`. Wire `complete(prompt, { system })` to any model you trust.

The `runner/mock-judge.mjs` heuristic is **for the demo and self-test only** — it
is language-blind and must not be used as a real measurement.

## Check tags as a rollup

`check_tags` lets you group fixtures into coverage categories — `intake`,
`truthfulness`, `guardrails`, `escalation`, `identity`, `behavior`,
`robustness` — and report a pass-rate per category instead of one flat number.

## Behavioral coverage, not an absolute score

Pass-rates depend on the judge model you bring. The rubric fields are written as
independently checkable assertions to reduce ambiguity, but cross-harness numbers
will not be identical. Treat the result as **coverage of known failure modes**,
and always report which judge you used. Text fixtures also give *behavioral*
coverage of noise/interruption handling — they do not prove a speech transcriber
survives real audio (that is the reserved `modality: "audio"` future work).
