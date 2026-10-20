/**
 * No-PII guard (zero-dependency).
 *
 * Every fixture in this repo is hand-authored and fictional. This scanner is a
 * backstop against an accidental paste of real call data: it flags
 * phone-shaped, email-shaped, and id-shaped strings that fall OUTSIDE the
 * reserved synthetic ranges. Synthetic data is expected and allowed — the guard
 * only fails on values that look real.
 *
 * Allowed (synthetic) by convention:
 *   - Phone numbers using exchange 555 and line 0100-0199 (the NANP fictional
 *     reservation), e.g. +1 (555) 555-0142.
 *   - Emails on reserved example domains (example.com / example.org / example.net).
 *   - The canonical payment test card 4111 1111 1111 1111.
 *
 * Flagged (looks real) -> non-zero exit:
 *   - Any other 10-digit North-American phone-shaped string.
 *   - Any email on a non-reserved domain.
 *   - UUID-shaped identifiers (internal id shape).
 *
 * Run with:  node scripts/check-no-pii.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, sep } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');

// Only data + docs are scanned for PII; the guard scripts and contributor docs
// describe the patterns themselves.
const SCANNED_EXTENSIONS = new Set(['.json', '.md', '.txt']);
const IGNORED_DIRS = new Set(['node_modules', '.git', 'dist', 'coverage']);
const IGNORED_FILES = new Set([
  'scripts/check-no-leak.mjs',
  'scripts/check-no-pii.mjs',
  'CONTRIBUTING.md',
]);

const ALLOWED_EMAIL_DOMAINS = new Set(['example.com', 'example.org', 'example.net']);
// Well-known, non-real payment test card used by safety fixtures.
const ALLOWED_CARDS = ['4111 1111 1111 1111', '4111111111111111'];

const EMAIL_RE = /[a-z0-9._%+-]+@([a-z0-9.-]+\.[a-z]{2,})/gi;
const UUID_RE = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;
// 10-digit NANP-shaped: optional +1, area, exchange, line, common separators.
const PHONE_RE = /(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})/g;

function isSyntheticPhone(area, exchange, line) {
  // Reserved fictional range: exchange 555, line 0100-0199 (any area code).
  if (exchange !== '555') return false;
  const n = Number(line);
  return n >= 100 && n <= 199;
}

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
function flag(rel, lineNo, label, value) {
  violations++;
  console.error(`PII [${label}] ${rel}:${lineNo}: ${value}`);
}

for (const file of walk(root)) {
  const rel = relative(root, file).split(sep).join('/');
  if (IGNORED_FILES.has(rel)) continue;
  const ext = file.slice(file.lastIndexOf('.'));
  if (!SCANNED_EXTENSIONS.has(ext)) continue;

  const rawLines = readFileSync(file, 'utf8').split(/\r?\n/);
  rawLines.forEach((rawLine, i) => {
    const lineNo = i + 1;

    // Strip allowed test cards before phone scanning so their digits don't trip it.
    let line = rawLine;
    for (const card of ALLOWED_CARDS) line = line.split(card).join(' ');

    // Emails
    for (const m of rawLine.matchAll(EMAIL_RE)) {
      const domain = m[1].toLowerCase();
      if (!ALLOWED_EMAIL_DOMAINS.has(domain)) flag(rel, lineNo, 'non-example email', m[0]);
    }

    // UUIDs
    const uuid = line.match(UUID_RE);
    if (uuid) flag(rel, lineNo, 'uuid-shaped id', uuid[0]);

    // Phone numbers
    for (const m of line.matchAll(PHONE_RE)) {
      const [full, area, exchange, lineDigits] = m;
      if (!isSyntheticPhone(area, exchange, lineDigits)) {
        flag(rel, lineNo, 'non-reserved phone-shaped string', full.trim());
      }
    }
  });
}

if (violations > 0) {
  console.error(`\nno-pii check FAILED with ${violations} violation(s).`);
  console.error('All fixtures must be synthetic. See CONTRIBUTING.md for the reserved ranges.');
  process.exit(1);
}
console.log('no-pii check passed: no real-looking PII found.');
