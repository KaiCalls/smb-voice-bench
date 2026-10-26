# Changelog

## Unreleased

`grade` command: an A to F letter over the seven cases from captured bundles (`--input`) or a scripted reference (`--agent`), written as `grade.json`, `GRADE.md` and `badge.svg`. Three mandatory cases cap the grade at D, unknown evidence never passes, and a missing case gives no letter. `--min-grade` gates CI. The repository is now a Claude Code plugin marketplace with a `smb-voice-bench` skill, and the README documents a one-line `uvx` install from git.

## 0.1.0 — 2026-10-20

External capture export: `write_external_bundle` builds manifests from bounded snapshots, retains original audio and explicit conditions, validates cross-file consistency before atomic publication, and rejects reference relabeling. Truncated caller scripts remain incomplete; changed or reordered turns are rejected. Unknown end times and nullable partial costs now remain incomplete instead of failing during parsing.

Initial offline package: seven frozen synthetic cases, audited SQLite tools, deterministic good/bad references, bounded evidence importer, independent assertions, evidence-bound review templates, conservative PCM measurements, explicit cohort comparison, static local reports and CLI. Initial public contract clarifications are documented in docs/CONTRACTS.md. Private legacy export stays outside the distribution. Standalone draft migration preserves the original JavaScript pack in a verified historical snapshot. Review gates now require statement and original-media citations, complete adjudication targets and chronological UTC timestamps. The maintainer authorized GitHub release publication; independent-person quickstart review remains unrecorded.
