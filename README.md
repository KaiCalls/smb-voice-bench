# SMB voice bench

Open-source tests for AI receptionists that book, correct, and recover from tool failures.

This local Python toolkit checks caller-authorized business outcomes against synthetic SQLite state and an independent attempt audit. It preserves unknown evidence, failed attempts, partial confirmation outcomes, and the difference between a prevented duplicate decision and a second committed booking.

**v0.1 is an offline engineering benchmark.** Its reference demonstrations are scripted text and tools. Audio is unavailable in bundled examples. Synthetic success makes no claim about revenue, customer conversion, compliance, carrier performance, or production readiness. External evidence is self-attested, not certification. A local confirmation record does not prove SMS or message delivery.

The original JavaScript fixture pack is preserved in [legacy/fixture-pack-v1](legacy/fixture-pack-v1/README.md). Its 25 fixtures and npm version are separate from this seven-scenario Python draft; see [migration notes](docs/MIGRATION.md).

## Release downloads

[v0.1.0 GitHub release](https://github.com/KaiCalls/smb-voice-bench/releases/tag/v0.1.0) provides the installable wheel, source archive, locked dependencies, checksums and signed build provenance. See [release installation and verification](docs/releases/v0.1.0.md). Distribution uses GitHub release assets; a PyPI upload is not configured.

## Quickstart

Use Python 3.10 or later on macOS or Linux/POSIX in an isolated environment. Descriptor-based no-follow filesystem checks are required; Windows is not supported in this initial version. CI checks Python 3.10 and 3.12. From this package directory:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps .
smb-voice-bench doctor --json
smb-voice-bench catalog
smb-voice-bench demo --output ./demo-report
```

Open `demo-report/index.html` directly. The faulty reference makes a second create decision after an unknown response; the sandbox prevents another booking and the evaluator still fails the attempt. The corrected reference reads the original booking status before recording one local confirmation. `demo` exits successfully only when it detects the expected failure and corrected functional pass. The comparison remains insufficient for release assessment because it covers one case and no speech or repeatability evidence.

The runtime commands never contact providers, read credentials, execute user-supplied code, load plugins, fetch remote media, or deliver messages. Dependency installation is a separate network operation. No account, telemetry, server framework, hosted dashboard, or automatic promotion is included.

## Seven scenarios

| ID | Independent outcome |
| --- | --- |
| `booking-and-confirmation` | One authorized Thursday booking and local confirmation |
| `duplicate-write-prevention` | A status request causes no second create decision |
| `unknown-write-reconciliation` | Verify the original committed booking after an unknown response |
| `partial-confirmation-failure` | Preserve the booking and report the failed confirmation honestly |
| `slow-lookup` | Exercise the 2500ms lookup fault before dependent actions |
| `interrupt-and-correct-context` | Respect Friday correction; text cannot prove audible interruption |
| `no-consent-no-write` | No mutation attempt after a decline |

All fixtures describe fictional Harbor Service Demo, Alex, a consultation, and fixed slots in America/Puerto_Rico. The suite manifest freezes revisions and canonical hashes. There are no real destinations or bundled recordings.

## Commands

```sh
smb-voice-bench simulate --scenario unknown-write-reconciliation --agent reference-good --output ./reference
smb-voice-bench validate --input ./reference --json
smb-voice-bench import --input ./reference --output ./imported
smb-voice-bench evaluate --input ./imported --output ./evaluation --scope functional
smb-voice-bench review-template --input ./imported --output ./human-review.json
smb-voice-bench evaluate --input ./imported --reviews ./reviews.json --output ./reviewed --scope audio-release
smb-voice-bench compare --baseline ./baseline.json --candidate ./candidate.json --change 'Describe the intended configuration change' --scope functional --output ./comparison
smb-voice-bench report --input ./evaluation --output ./rendered-report
```

Outputs are new private directories or a new review file; overwrite is refused. Parent directories must already exist. Resolve operating-system aliases such as `/tmp` to their real directory (often `/private/tmp` on macOS): every filesystem component is checked for symlinks. Failed/interrupted staging directories retain an `.incomplete-smb-` prefix. Do not reuse an unknown operation to obtain a fresh attempt.

A run selector is `{"kind":"run_list","schema_version":"0.1.0","paths":["runs/first","runs/second"]}`. A review selector uses `kind: "review_list"` and paths to review JSON files. Paths are relative to the selector; URLs, traversal and symlinks are rejected. Review sidecars stay outside immutable source bundles. Comparison arms must have disjoint run IDs. Every requested path must resolve.

All commands support `--json`. JSON goes to stdout and diagnostics to stderr. Exit codes: `0` command/requested scope completed successfully; `1` behavioral failure or blocked candidate; `2` missing/insufficient evidence; `3` invalid arguments, integrity or operational error. `simulate` produces evidence; it is not an assessment. `report` renders existing judgments; it is not a new passing evaluation.

## Use your own harness

See [the integration guide](docs/INTEGRATION.md), [contracts](docs/CONTRACTS.md), and [local conformance writer](examples/conformance_writer.py). The integration guide includes `write_external_bundle`, a Python helper that builds and validates manifests from captured snapshots. Your external harness owns runtime transport and produces local evidence; the public CLI never launches it. Native audio and cascaded agents use the same evidence contract. Pass only the current completed caller turn, neutral business context and tool responses to the agent. Future turns, permissions, audit handles and expected outputs belong to the harness.

Use personal or synthetic local audio only. Original media stays immutable; normalization must create a separately hashed derivative. Unsupported/missing media leaves audio dimensions unknown. No automatic audio conversion is performed in this version. A real-agent truthful-status verdict requires evidence-bound human review; text matching never clears it. Truthfulness reviews must cite an assistant statement in the events artifact; audio reviews also cite the retained original recording. Listening requires readable canonical PCM audio, two distinct completed human reviewers and ratings of at least 4/5. Review identity is provenance, not authenticated identity proof.

Functional, evidence, truthfulness, timing, listening and repeatability are separate verdicts. `audio-release` additionally requires all seven scenarios, five completed observations per unchanged configuration, actual media, two completed human reviews per run and the timing policy. A single-run audio assessment cannot satisfy repeatability. Any selected critical failure blocks either scope, even if the sandbox prevented the action. Eligibility is permission to review lab evidence, never permission to deploy.

## Implementation acceptance

The offline v0.1 implementation is complete for the seven-scenario scope. See [acceptance evidence and reproduction](docs/ACCEPTANCE.md). To exercise every installed command, run `python /absolute/checkout/tools/verify_install.py --output ./acceptance-report` from a separate temporary directory with `PYTHONPATH` unset. This checks actual installed code, reference outcomes, imports, report regeneration and failure paths without network or credentials. The maintainer authorized the initial GitHub engineering release after automated acceptance; an independent-person quickstart has not been recorded.

## Develop and contribute

Run one package-local process: `python -m unittest discover -s tests -v`. No monorepo build or live call is needed. [CONTRIBUTING](CONTRIBUTING.md) describes synthetic case changes and negative controls. [Methods](docs/METHODS.md) defines metrics and limitations. [Release review](docs/RELEASE.md) lists remaining human/release gates. Code, synthetic fixtures and documentation use MIT; see [provenance](THIRD_PARTY_NOTICES.md).
