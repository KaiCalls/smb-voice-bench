/**
 * No-runtime-leak guard (zero-dependency).
 *
 * Greps every shipped text file for tokens that would leak proprietary or
 * runtime-specific details, and exits non-zero on any hit. The public artifact
 * must never name a specific voice runtime as "our" runtime, never expose
 * internal database column/table names, and never reference internal infra.
 *
 * Carve-out by convention: a top-level `adapters/` directory may name specific
 * harnesses/runtimes — but ONLY as peer providers, listed alphabetically with
 * equal billing. Brand-name rules are relaxed inside `adapters/`; the
 * database / infra / id rules are enforced everywhere, with no exceptions.
 *
 * Run with:  node scripts/check-no-leak.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, sep } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

const SCANNED_EXTENSIONS = new Set(['.json', '.md', '.mjs', '.js', '.ts', '.txt', '.yml', '.yaml']);
const IGNORED_DIRS = new Set(['node_modules', '.git', 'dist', 'coverage']);

// Files that legitimately contain the forbidden tokens (as prose about the rule
// itself) and must be excluded from their own scan.
const IGNORED_FILES = new Set([
  'scripts/check-no-leak.mjs',
  'scripts/check-no-pii.mjs',
  'CONTRIBUTING.md',
]);

// Each rule: a label + RegExp. `allowInAdapters` relaxes brand-only rules inside
// the adapters/ carve-out; db/infra/id rules stay enforced everywhere.
const FORBIDDEN = [
  { label: 'voice-runtime brand name', re: /\bvapi\b/i, allowInAdapters: true },
  { label: 'internal tenant column (business_id)', re: /business_id/i, allowInAdapters: false },
  { label: 'internal customer_ column prefix', re: /customer_[a-z]/i, allowInAdapters: false },
  { label: 'internal agent column (vapi_assistant_id / agent_assignments)', re: /vapi_assistant_id|agent_assignments/i, allowInAdapters: false },
  { label: 'CRM provider name (GoHighLevel)', re: /gohighlevel|leadconnectorhq/i, allowInAdapters: false },
  { label: 'CRM adapter key (locationId)', re: /\blocationId\b/, allowInAdapters: false },
  { label: 'legal CRM name (Litify)', re: /\blitify\b/i, allowInAdapters: false },
  { label: 'CRM adapter keys (sforgid/externalId)', re: /\bsforgid\b|\bexternalId\b/i, allowInAdapters: false },
  { label: 'backend platform name (Supabase)', re: /supabase/i, allowInAdapters: false },
  { label: 'internal infra host (kaicalls.co / *.supabase.co)', re: /kaicalls\.co\b|\.supabase\.co/i, allowInAdapters: false },
  { label: 'brittle raw GitHub schema URL', re: /raw\.githubusercontent\.com/i, allowInAdapters: false },
];

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const rel = relative(root, full);
    const top = rel.split(sep)[0];
    if (IGNORED_DIRS.has(entry) || IGNORED_DIRS.has(top)) continue;
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

let violations = 0;
for (const file of walk(root)) {
  const rel = relative(root, file).split(sep).join('/');
  if (IGNORED_FILES.has(rel)) continue;
  const ext = file.slice(file.lastIndexOf('.'));
  if (!SCANNED_EXTENSIONS.has(ext)) continue;

  const inAdapters = rel.startsWith('adapters/');
  const lines = readFileSync(file, 'utf8').split(/\r?\n/);
  lines.forEach((line, i) => {
    for (const { label, re, allowInAdapters } of FORBIDDEN) {
      if (inAdapters && allowInAdapters) continue;
      if (re.test(line)) {
        violations++;
        console.error(`LEAK [${label}] ${rel}:${i + 1}: ${line.trim()}`);
      }
    }
  });
}

if (violations > 0) {
  console.error(`\nno-leak check FAILED with ${violations} violation(s).`);
  process.exit(1);
}
console.log('no-leak check passed: no forbidden tokens found.');
