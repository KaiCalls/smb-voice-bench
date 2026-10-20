# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the package version
follows [Semantic Versioning](https://semver.org/).

## Schema vs. package versioning (policy for consumers who pin fixtures)

There are **two** version numbers, on purpose:

- **Package version** (`package.json` `version`, e.g. `1.0.0`) — SemVer over the
  whole repo: fixtures, runner, adapters, docs.
- **Fixture schema version** (`schemaVersion` field on every fixture, e.g.
  `"smb-voice-bench/v1"`) — the contract a consumer's loader/validator pins to.

Promises for anyone depending on field stability:

1. **No breaking change to existing `schemaVersion` fields within a major schema
   version.** Within `smb-voice-bench/v1` we will not remove or repurpose a
   documented field, or change a field's type/meaning. New *optional* fields and
   new enum values (e.g. a new `vertical`) are **additive** and ship in minor
   package releases.
2. **A breaking schema change bumps the schema id** (`smb-voice-bench/v2`) and
   the package **major**. Both schema versions can co-exist during a deprecation
   window; the deprecation is announced here at least one minor release ahead.
3. **Fixture content can change in any release** (new scenarios, reworded
   rubric/criteria). If you need byte-stable fixtures, pin an exact package
   version. Pass-rates are behavioral coverage, not a frozen score (see
   [docs/scoring-and-judging.md](docs/scoring-and-judging.md)).

## [1.0.0] - 2026-06-27

### Added

- 25 hand-authored, fully synthetic SMB receptionist scenarios across 8 verticals
  plus a `universal` baseline, conforming to `schema/scenario.schema.json`
  (`schemaVersion: "smb-voice-bench/v1"`).
- Versioned JSON Schema, the six-mode failure taxonomy, and structured
  `expected_intake_fields` with a shared intake vocabulary.
- Standalone reference runner (`runner/`) and a worked, runnable
  bring-your-own-agent example with a real LLM judge (`examples/run-your-agent.mjs`)
  plus a stdlib-only Python consumption example (`examples/python/run_bench.py`).
- `loadScenarios()` now defaults to the bundled fixtures, so it works from a
  clone or an installed dependency with no hardcoded `node_modules/` path.
- Mapping-adapter templates for ServiceNow EVA and LiveKit Agents (`adapters/`),
  with smoke-test coverage in CI.
- Two CI guards: no-PII (`lint:no-pii`) and no-runtime-leak (`lint:no-leak`).
