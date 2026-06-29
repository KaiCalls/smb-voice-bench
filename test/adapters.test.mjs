/**
 * Adapter smoke tests.
 *
 * The adapter converters are honest STARTING POINTS (see adapters/README.md),
 * but a regression that makes them throw or drop scenarios should still fail CI.
 * These tests assert the converters faithfully map every fixture: every scenario
 * converts, ids/names are preserved, the rubric parts survive, and the blocking
 * flag tracks `severity: "critical"`.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadScenarios } from '../runner/runner.mjs';
import { toEvaScenario } from '../adapters/eva/convert.mjs';
import { toLiveKitSpec } from '../adapters/livekit/convert.mjs';

const scenarios = loadScenarios();
const criticalIds = new Set(scenarios.filter((s) => s.severity === 'critical').map((s) => s.id));

test('EVA converter maps every fixture faithfully', () => {
  const out = scenarios.map(toEvaScenario);
  assert.equal(out.length, scenarios.length);
  for (const [i, e] of out.entries()) {
    const s = scenarios[i];
    assert.equal(e.id, s.id, 'id preserved');
    assert.ok(Array.isArray(e.rubric.must) && e.rubric.must.length >= 1, 'rubric.must populated');
    assert.equal(
      e.extraction_checks.length,
      s.expected_intake_fields.length,
      'one extraction check per expected_intake_field',
    );
    assert.equal(e.blocking, criticalIds.has(s.id), 'blocking tracks severity:critical');
  }
  assert.equal(out.filter((e) => e.blocking).length, criticalIds.size, 'blocking count matches critical count');
});

test('LiveKit converter maps every fixture faithfully', () => {
  const out = scenarios.map(toLiveKitSpec);
  assert.equal(out.length, scenarios.length);
  for (const [i, l] of out.entries()) {
    const s = scenarios[i];
    assert.equal(l.name, s.id, 'name = id');
    assert.ok(Array.isArray(l.judge_assertions.should) && l.judge_assertions.should.length >= 1, 'should populated');
    assert.equal(
      l.extraction_assertions.length,
      s.expected_intake_fields.length,
      'one extraction assertion per expected_intake_field',
    );
    assert.equal(l.blocking, criticalIds.has(s.id), 'blocking tracks severity:critical');
  }
});
