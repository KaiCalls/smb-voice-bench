/**
 * CI validator: every fixture under scenarios/ validates against
 * schema/scenario.schema.json, plus a few cross-field invariants the JSON Schema
 * cannot easily express.
 *
 *   node --test    (ajv + ajv-formats are devDependencies)
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname, relative } from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const schemaPath = join(root, 'schema', 'scenario.schema.json');
const scenariosDir = join(root, 'scenarios');

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function loadScenarioFiles(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) loadScenarioFiles(full, out);
    else if (extname(full) === '.json') out.push(full);
  }
  return out;
}

const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
const validate = ajv.compile(readJson(schemaPath));

const files = loadScenarioFiles(scenariosDir);

test('there are at least 20 scenarios', () => {
  assert.ok(files.length >= 20, `expected >= 20 scenarios, found ${files.length}`);
});

const seenIds = new Set();

for (const file of files) {
  const rel = relative(root, file).split('\\').join('/');
  test(`${rel} validates against the scenario schema`, () => {
    const scenario = readJson(file);
    const ok = validate(scenario);
    assert.ok(ok, `schema errors: ${ajv.errorsText(validate.errors)}`);
  });

  test(`${rel} has a unique id matching its namespace`, () => {
    const scenario = readJson(file);
    assert.ok(!seenIds.has(scenario.id), `duplicate id ${scenario.id}`);
    seenIds.add(scenario.id);
    // id namespace must agree with the declared vertical.
    const parts = scenario.id.split('.');
    assert.equal(parts[0], 'smbvb');
    assert.equal(parts[1], scenario.vertical, `id vertical segment must equal vertical field`);
  });

  test(`${rel} has at least one judged agent turn`, () => {
    const scenario = readJson(file);
    const judged = scenario.script.filter((t) => t.role === 'agent' && t.judged === true);
    assert.ok(judged.length >= 1, 'needs >=1 judged agent turn');
  });

  test(`${rel} has at least one required expected_intake_field OR documents why not`, () => {
    const scenario = readJson(file);
    // Spam/injection fixtures intentionally capture nothing; they use notes to
    // document the negative. Either at least one required field, or every field
    // carries a note explaining the negative-intake intent.
    const hasRequired = scenario.expected_intake_fields.some((f) => f.required === true);
    const allDocumented = scenario.expected_intake_fields.every((f) => typeof f.notes === 'string');
    assert.ok(hasRequired || allDocumented, 'either a required intake field or documented negative-intake');
  });
}
