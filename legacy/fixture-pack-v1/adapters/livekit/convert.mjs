/**
 * LiveKit adapter — converter stub.
 *
 * Maps each smb-voice-bench Scenario into an illustrative LiveKit-style test
 * spec: the caller turns to drive plus judge / extraction assertions. The
 * emitted shape is a STARTING POINT; adapt it to the agents.test + judge API
 * version you run. This file is a peer adapter — it does not replace LiveKit.
 *
 *   node adapters/livekit/convert.mjs            # print to stdout
 *   node adapters/livekit/convert.mjs --out DIR  # one JSON file per scenario
 */

import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';
import { mkdirSync, writeFileSync, readFileSync, readdirSync, statSync } from 'node:fs';

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

/** Map one Scenario -> illustrative LiveKit test spec. */
export function toLiveKitSpec(s) {
  return {
    name: s.id,
    description: s.title,
    context: {
      goal: s.caller_goal,
      business: s.business_context,
    },
    turns: s.script
      .filter((t) => t.role === 'caller')
      .map((t) => ({ user: t.content })),
    judge_assertions: {
      should: s.success_criteria,
      should_not: [
        ...(s.must_not_claim ?? []),
        ...s.failure_traps.map((t) => `[${t.mode}] ${t.description}`),
      ],
      should_escalate_if: s.must_escalate_if ?? [],
    },
    extraction_assertions: s.expected_intake_fields.map((f) => ({
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
  const converted = scenarios.map(toLiveKitSpec);

  if (outDir) {
    mkdirSync(outDir, { recursive: true });
    for (const c of converted) {
      writeFileSync(join(outDir, `${c.name}.json`), JSON.stringify(c, null, 2));
    }
    console.error(`Wrote ${converted.length} LiveKit-style specs to ${outDir}`);
  } else {
    process.stdout.write(JSON.stringify(converted, null, 2) + '\n');
  }
}

if (import.meta.url === `file://${process.argv[1]}` || process.argv[1]?.endsWith('convert.mjs')) {
  main();
}
