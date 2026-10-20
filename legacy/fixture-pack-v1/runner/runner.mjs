/**
 * Standalone reference runner (dependency-light).
 *
 * Proves the scenario schema is runnable end to end. It is intentionally NOT a
 * framework: it replays a scenario's `caller` turns to an agent-under-test you
 * supply, sends each judged turn plus the scenario rubric to a pluggable judge,
 * and aggregates results with the contract:
 *
 *   - a judged turn passes iff the judge returns `pass`
 *   - a scenario passes iff EVERY judged turn passes
 *   - a suite reports pass-rate; a failing `critical` (blocking) scenario is
 *     surfaced separately so a caller can fail-closed on it
 *
 * The agent-under-test is any function `(messages) => reply | Promise<reply>`
 * where `messages` is the conversation so far as `{ role, content }` objects
 * (`role` is `"caller"` or `"agent"`) and `reply` is the agent's next utterance.
 * The judge is any function `({ scenario, messages, reply }) => { pass, reasons }`.
 * Bring your own model for the judge (see judge.mjs) or use the demo mock judge.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Absolute path to the scenario fixtures bundled with this package.
 * Resolved relative to this file, so it works the same whether the package is
 * a local `git clone` checkout or installed under `node_modules` — no need to
 * know or hardcode `node_modules/@kaicalls/smb-voice-bench/scenarios`.
 */
export const SCENARIOS_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'scenarios');

/**
 * Recursively load every scenario JSON file under a directory.
 * Defaults to the bundled fixtures ({@link SCENARIOS_DIR}) when called with no
 * argument, so `loadScenarios()` works out of the box from a clone or an
 * installed dependency.
 * @param {string} [dir] directory to load from (defaults to the bundled fixtures)
 * @returns {object[]} parsed scenarios
 */
export function loadScenarios(dir = SCENARIOS_DIR) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...loadScenarios(full));
    } else if (extname(full) === '.json') {
      out.push(JSON.parse(readFileSync(full, 'utf8')));
    }
  }
  return out;
}

/** Whether a scenario should fail the whole run if it fails. */
export function isBlocking(scenario) {
  return scenario.severity === 'critical';
}

/**
 * Run one scenario against an agent + judge.
 * @param {object} scenario
 * @param {(messages: {role: string, content: string}[]) => (string|Promise<string>)} agentFn
 * @param {(args: object) => ({pass: boolean, reasons?: string[]}|Promise<{pass: boolean, reasons?: string[]}>)} judge
 */
export async function runScenario(scenario, agentFn, judge) {
  const transcript = [];
  const turnResults = [];

  for (const turn of scenario.script) {
    if (turn.role === 'caller') {
      transcript.push({ role: 'caller', content: turn.content ?? '' });
      continue;
    }
    // agent turn
    if (turn.judged) {
      const context = transcript.map((t) => ({ ...t }));
      const reply = await agentFn(context);
      const verdict = await judge({ scenario, messages: context, reply });
      turnResults.push({
        turnIndex: scenario.script.indexOf(turn),
        pass: !!verdict.pass,
        reasons: verdict.reasons ?? [],
        reply,
      });
      transcript.push({ role: 'agent', content: reply });
    } else {
      transcript.push({ role: 'agent', content: turn.content ?? '' });
    }
  }

  const pass = turnResults.length > 0 && turnResults.every((r) => r.pass);
  return {
    id: scenario.id,
    vertical: scenario.vertical,
    severity: scenario.severity ?? 'medium',
    blocking: isBlocking(scenario),
    pass,
    turnResults,
    transcript,
  };
}

/**
 * Run a suite of scenarios and aggregate.
 * @returns {{ total: number, passed: number, passRate: number, blockingFailed: string[], results: object[] }}
 */
export async function runSuite(scenarios, agentFn, judge) {
  const results = [];
  for (const scenario of scenarios) {
    results.push(await runScenario(scenario, agentFn, judge));
  }
  const passed = results.filter((r) => r.pass).length;
  const blockingFailed = results.filter((r) => r.blocking && !r.pass).map((r) => r.id);
  return {
    total: results.length,
    passed,
    passRate: results.length ? passed / results.length : 0,
    blockingFailed,
    results,
  };
}
