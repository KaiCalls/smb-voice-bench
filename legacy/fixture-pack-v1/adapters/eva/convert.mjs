/**
 * EVA adapter — converter stub.
 *
 * Maps each smb-voice-bench Scenario into an illustrative EVA-shaped scenario
 * object (simulated caller + expected-behavior rubric + extraction checks).
 * The emitted field names are a STARTING POINT; pin them to the EVA version you
 * run. This file is a peer adapter — it does not replace EVA.
 *
 *   node adapters/eva/convert.mjs            # print to stdout
 *   node adapters/eva/convert.mjs --out DIR  # one JSON file per scenario
 */

import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdirSync, writeFileSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { extname } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const scenariosDir = join(here, '..', '..', 'scenarios');

function loadScenarios(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) loadScenarios(full, out);
    else if (extname(full) === '.json') out.push(JSON.parse(readFileSync(full, 'utf8')));
  }
  return out;
}

/** Map one Scenario -> illustrative EVA scenario. */
export function toEvaScenario(s) {
  const callerTurns = s.script.filter((t) => t.role === 'caller').map((t) => t.content);
  return {
    id: s.id,
    title: s.title,
    persona: {
      goal: s.caller_goal,
      opening_turns: callerTurns,
    },
    world_context: s.business_context,
    rubric: {
      must: s.success_criteria,
      must_not: [
        ...(s.must_not_claim ?? []),
        ...s.failure_traps.map((t) => `[${t.mode}] ${t.description}`),
      ],
      must_escalate_if: s.must_escalate_if ?? [],
    },
    extraction_checks: s.expected_intake_fields.map((f) => ({
      field: f.field,
      required: f.required,
      expected_value: f.expected_value,
    })),
    blocking: s.severity === 'critical',
  };
}

function main() {
  const args = process.argv.slice(2);
  const outIdx = args.indexOf('--out');
  const outDir = outIdx >= 0 ? args[outIdx + 1] : null;
  const scenarios = loadScenarios(scenariosDir);
  const converted = scenarios.map(toEvaScenario);

  if (outDir) {
    mkdirSync(outDir, { recursive: true });
    for (const c of converted) {
      writeFileSync(join(outDir, `${c.id}.json`), JSON.stringify(c, null, 2));
    }
    console.error(`Wrote ${converted.length} EVA-shaped scenarios to ${outDir}`);
  } else {
    process.stdout.write(JSON.stringify(converted, null, 2) + '\n');
  }
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith('convert.mjs')) {
  main();
}
