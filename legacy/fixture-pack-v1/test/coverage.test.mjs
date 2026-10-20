/**
 * Coverage guards: the fixture set must cover all six failure modes and the
 * full vertical set, so coverage cannot silently regress.
 *
 *   node --test
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const scenariosDir = join(root, 'scenarios');

function loadScenarios(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) loadScenarios(full, out);
    else if (extname(full) === '.json') out.push(JSON.parse(readFileSync(full, 'utf8')));
  }
  return out;
}

const scenarios = loadScenarios(scenariosDir);

// Single source of truth: the `vertical` enum lives in the schema. Deriving it
// here means adding a vertical to the schema enum automatically requires a
// fixture for it (see CONTRIBUTING.md "Adding a new vertical").
const schema = JSON.parse(readFileSync(join(root, 'schema', 'scenario.schema.json'), 'utf8'));
const ALL_VERTICALS = schema.properties.vertical.enum;

const ALL_MODES = [
  'hallucinated_pricing',
  'invented_policy',
  'missing_intake',
  'failure_to_escalate',
  'mishandled_interruption',
  'unsafe_overconfident',
];


test('all six failure modes are exercised by >=1 fixture', () => {
  const seen = new Set();
  for (const s of scenarios) for (const t of s.failure_traps) seen.add(t.mode);
  for (const mode of ALL_MODES) assert.ok(seen.has(mode), `no fixture exercises mode "${mode}"`);
});

test('every declared vertical has >=1 fixture', () => {
  const seen = new Set(scenarios.map((s) => s.vertical));
  for (const v of ALL_VERTICALS) assert.ok(seen.has(v), `no fixture for vertical "${v}"`);
});

test('covers at least 4 verticals (issue floor) and 8 business verticals (plan)', () => {
  const business = new Set(scenarios.map((s) => s.vertical));
  business.delete('universal');
  assert.ok(business.size >= 4, `expected >=4 business verticals, got ${business.size}`);
  assert.ok(business.size >= 8, `plan targets 8 business verticals, got ${business.size}`);
});

test('every escalation-required scenario carries an escalation/guardrails tag', () => {
  for (const s of scenarios) {
    const escalates = (s.must_escalate_if ?? []).length > 0 ||
      s.failure_traps.some((t) => t.mode === 'failure_to_escalate');
    if (!escalates) continue;
    const tags = s.check_tags ?? [];
    assert.ok(
      tags.includes('escalation') || tags.includes('guardrails'),
      `${s.id} escalates but is not tagged escalation/guardrails`,
    );
  }
});

test('every critical scenario is treated as a guardrail/escalation fixture', () => {
  for (const s of scenarios) {
    if (s.severity !== 'critical') continue;
    const tags = s.check_tags ?? [];
    assert.ok(
      tags.includes('guardrails') || tags.includes('escalation'),
      `${s.id} is critical but not tagged guardrails/escalation`,
    );
  }
});
