/**
 * Worked example: run the bench against YOUR agent with a REAL LLM judge.
 *
 * This is the copy-paste-and-edit starting point the README points to. It runs
 * verbatim from a local checkout:
 *
 *   node examples/run-your-agent.mjs
 *
 * Two things you swap for your own:
 *   1) `myAgent` — replace with a call to your agent-under-test. The contract is
 *      `(messages) => reply`, where `messages` is `[{ role:'caller'|'agent', content }]`.
 *      v1 is text-only; for a live phone/voice agent, wrap it in a function that
 *      takes the caller transcript and returns the agent's text reply.
 *   2) the judge — set JUDGE_API_KEY / JUDGE_BASE_URL / JUDGE_MODEL (see
 *      .env.example) and this uses a REAL model. With no key it falls back to the
 *      bundled mock judge and prints a loud warning (the mock is NOT a real
 *      measurement).
 *
 * Imports are RELATIVE (./..) so this works in a `git clone` checkout. If you
 * instead installed the package as a dependency, import from the package name:
 *   import { loadScenarios, runSuite } from '@kaicalls/smb-voice-bench/runner/runner.mjs';
 *   import { makeLLMJudge } from '@kaicalls/smb-voice-bench/runner/judge.mjs';
 */

import { loadScenarios, runSuite } from '../runner/runner.mjs';
import { makeLLMJudge, JUDGE_SYSTEM } from '../runner/judge.mjs';
import { makeMockJudge } from '../runner/mock-judge.mjs';

// 1) YOUR AGENT-UNDER-TEST. Replace this stub with a call to your agent.
//    This naive stub just greets and asks for a name + callback — it will
//    (correctly) fail the life-safety scenarios because it never escalates.
async function myAgent(messages) {
  const lastCaller = [...messages].reverse().find((m) => m.role === 'caller');
  void lastCaller;
  return "Thanks for calling! I can take a message — can I get your name and the best callback number?";
}

/**
 * A real judge backed by any OpenAI-compatible Chat Completions endpoint.
 * Returns a `complete(prompt, { system }) => "pass"|"fail"` function, which is
 * exactly what `makeLLMJudge` expects.
 */
function openaiCompatibleComplete({ baseUrl, model, apiKey }) {
  return async (prompt, { system }) => {
    const res = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        temperature: 0,
        max_tokens: 8,
        messages: [
          { role: 'system', content: system ?? JUDGE_SYSTEM },
          { role: 'user', content: prompt },
        ],
      }),
    });
    if (!res.ok) {
      throw new Error(`judge API ${res.status}: ${await res.text()}`);
    }
    const data = await res.json();
    return data.choices?.[0]?.message?.content ?? 'fail';
  };
}

function resolveJudge() {
  const { JUDGE_API_KEY, JUDGE_BASE_URL, JUDGE_MODEL } = process.env;
  if (JUDGE_API_KEY && JUDGE_BASE_URL && JUDGE_MODEL) {
    console.log(`Judge: ${JUDGE_MODEL} via ${JUDGE_BASE_URL} (real LLM judge)\n`);
    return makeLLMJudge(
      openaiCompatibleComplete({ baseUrl: JUDGE_BASE_URL, model: JUDGE_MODEL, apiKey: JUDGE_API_KEY }),
    );
  }
  console.warn(
    '!! No JUDGE_API_KEY/JUDGE_BASE_URL/JUDGE_MODEL set — falling back to the MOCK judge.\n' +
      '!! The mock judge is a heuristic, NOT a real measurement. Copy .env.example to .env\n' +
      '!! and set a real model for a real pass/fail score.\n',
  );
  return makeMockJudge();
}

async function main() {
  const scenarios = loadScenarios(); // bundled fixtures; pass a dir to override
  const judge = resolveJudge();
  const report = await runSuite(scenarios, myAgent, judge);

  console.log(`Loaded ${scenarios.length} scenarios.`);
  console.log(`${report.passed}/${report.total} passed (${(report.passRate * 100).toFixed(0)}%)`);
  if (report.blockingFailed.length) {
    console.error(`Blocking (critical) scenarios failed: ${report.blockingFailed.join(', ')}`);
    process.exitCode = 1; // fail-closed on safety fixtures
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
