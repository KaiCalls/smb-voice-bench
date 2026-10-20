# Examples

Copy-paste-and-edit starting points for running the bench against your own
agent. All run **verbatim from a local checkout** (`git clone` then `cd`), no
publish required.

| File | Language | What it shows |
|------|----------|---------------|
| [`run-your-agent.mjs`](run-your-agent.mjs) | Node (JS) | Full path: relative imports, `loadScenarios()`, your agent-under-test, and a **real** LLM judge against any OpenAI-compatible endpoint (falls back to the mock judge with a loud warning if no key). |
| [`python/run_bench.py`](python/run_bench.py) | Python (stdlib only) | The fixtures are language-neutral JSON — this is the drop-in for Python harnesses (ServiceNow EVA, LiveKit Agents). Loads fixtures, mirrors the grading contract, real or offline-stub judge. |

## Run the JS example

```bash
node examples/run-your-agent.mjs
```

With no judge configured it uses the mock judge (NOT a real score). For a real
measurement, copy [`.env.example`](../.env.example) to `.env`, set a real model,
then:

```bash
# requires Node 20.6+ for --env-file (or just export the vars yourself)
node --env-file=.env examples/run-your-agent.mjs
```

## Run the Python example

```bash
python examples/python/run_bench.py            # offline stub judge
JUDGE_API_KEY=... JUDGE_BASE_URL=https://api.openai.com/v1 JUDGE_MODEL=gpt-4o-mini \
  python examples/python/run_bench.py          # real LLM judge
```

## Bringing your own agent

The agent-under-test contract is **text-only** in v1: `(messages) => reply`,
where `messages` is `[{ role: 'caller' | 'agent', content }]`. For a live
phone/voice agent, write a thin shim that feeds the caller transcript in and
returns your agent's text reply — see the [Roadmap](../README.md#roadmap-deferred)
for the planned audio modality.
