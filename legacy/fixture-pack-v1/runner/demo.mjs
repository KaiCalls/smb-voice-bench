/**
 * Runnable demo: load every fixture, run the safe stub and the reckless stub
 * through the standalone runner with the (demo-only) mock judge, and print the
 * pass-rates side by side.
 *
 *   npm run demo
 *
 * This uses the language-blind mock judge, so the numbers only prove the
 * plumbing — a safe agent passes, a reckless agent fails. For a real run, swap
 * in `makeLLMJudge` from judge.mjs with a model you trust.
 */

import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { loadScenarios, runSuite, runScenario } from './runner.mjs';
import { makeMockJudge } from './mock-judge.mjs';
import { makeGoodAgent, makeBadAgent } from './stub-agents.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const scenariosDir = join(here, '..', 'scenarios');

const scenarios = loadScenarios(scenariosDir);
const judge = makeMockJudge();

// goodAgent branches per scenario, so run scenario-by-scenario.
async function runWithGood() {
  const results = [];
  for (const s of scenarios) results.push(await runScenario(s, makeGoodAgent(s), judge));
  const passed = results.filter((r) => r.pass).length;
  return { total: results.length, passed, passRate: passed / results.length };
}

const good = await runWithGood();
const bad = await runSuite(scenarios, makeBadAgent(), judge);

const pct = (n) => `${(n * 100).toFixed(0)}%`;
console.log(`Loaded ${scenarios.length} scenarios.\n`);
console.log(`Safe stub agent:     ${good.passed}/${good.total} passed (${pct(good.passRate)})`);
console.log(`Reckless stub agent: ${bad.passed}/${bad.total} passed (${pct(bad.passRate)})`);
console.log(`Reckless blocking failures: ${bad.blockingFailed.length}`);
console.log('\n(Demo mock judge only — not a real measurement. See runner/README.md.)');
