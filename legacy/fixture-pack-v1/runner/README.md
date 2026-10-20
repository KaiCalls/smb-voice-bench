# Standalone reference runner

> **Disclaimer — not legal or safety advice.** These scenarios include
> safety-adjacent situations (emergencies, medical/legal questions). They model
> *behavioral coverage* for testing an agent; they do not implement, guarantee,
> or replace any emergency-response, medical, legal, privacy, or
> consumer-protection obligation. Escalation behavior and any regulated handling
> are the integrator's responsibility.

A tiny, dependency-free runner that proves the scenario schema is runnable. It
is **not a framework** — it is the smallest thing that demonstrates the grading
contract so the same fixtures can be driven by a real harness (see
[`../adapters/`](../adapters/)).

## The contract

- A judged turn **passes** iff the judge returns `pass`.
- A scenario **passes** iff **every** judged turn passes.
- A suite reports a **pass-rate**; a failing `critical` (blocking) scenario is
  surfaced in `blockingFailed` so a caller can fail-closed on safety fixtures.

## Pieces

| File | Role |
|------|------|
| `runner.mjs` | `loadScenarios(dir)`, `runScenario(scenario, agentFn, judge)`, `runSuite(scenarios, agentFn, judge)`. |
| `judge.mjs` | `makeLLMJudge(complete)` — **bring your own model**. Renders the rubric into a `pass`/`fail` prompt. This is the judge you should use for real runs. |
| `mock-judge.mjs` | `makeMockJudge()` — a deterministic, language-blind heuristic for the demo + self-test only. **Not a real evaluator.** |
| `stub-agents.mjs` | A safe stub and a reckless stub, used to self-test the runner. |
| `demo.mjs` | `npm run demo` — runs both stubs through the mock judge. |

## Plug in your agent and judge

For a complete runnable version (real LLM judge + env wiring), see
[`../examples/run-your-agent.mjs`](../examples/run-your-agent.mjs). The minimal
shape:

```js
// Local checkout (after `git clone`): import via relative paths.
import { loadScenarios, runSuite } from './runner.mjs';
import { makeLLMJudge } from './judge.mjs';
// Installed as a dependency instead?
//   import { loadScenarios, runSuite } from '@kaicalls/smb-voice-bench/runner/runner.mjs';
//   import { makeLLMJudge } from '@kaicalls/smb-voice-bench/runner/judge.mjs';

// 1. Your agent-under-test: (messages) => assistant reply
//    messages is the conversation so far: [{ role: 'caller'|'agent', content }]
const agent = async (messages) => myAgent.reply(messages);

// 2. Your judge model: (prompt, { system }) => "pass" | "fail"
const judge = makeLLMJudge(async (prompt, { system }) =>
  myModel.complete({ system, prompt }),
);

const scenarios = loadScenarios(); // defaults to the bundled fixtures
const report = await runSuite(scenarios, agent, judge);

console.log(`${report.passed}/${report.total} passed (${(report.passRate * 100).toFixed(0)}%)`);
if (report.blockingFailed.length) {
  console.error('Blocking (critical) scenarios failed:', report.blockingFailed);
  process.exit(1);
}
```

## On comparability

The bench measures **behavioral coverage**, not an absolute score. Pass-rates
depend on the judge model you bring; the rubric fields are written as
independently checkable assertions to reduce ambiguity, but cross-harness
numbers will not be identical. Report which judge you used.
