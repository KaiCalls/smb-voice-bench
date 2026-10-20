# Evidence contracts 0.1.0

The installed local registry is `smb_voice_bench/schemas/contracts.schema.json`. All supported source documents have closed top-level properties, a `kind`, and `schema_version: "0.1.0"`. Unsupported versions fail; there is no silent migration, remote schema resolution, templating or code execution. Extensions require namespaced keys, are capped at 64 KiB and do not contribute to grading.

Canonical identity is SHA-256 of UTF-8 JSON with sorted keys, compact separators, Unicode preserved and nonfinite numbers forbidden. Artifact hashes cover exact retained bytes. The manifest identity covers its canonical JSON; it has no circular self-hash. Review and result sidecars bind to that identity outside the source bundle.

A source directory contains `manifest.json` and the manifest's scenario, sanitized configuration, event JSONL and sandbox-state artifacts. An audio source stays audio even if its recording is missing. An unavailable run end time remains null and makes the run incomplete. Partial cost components may be null; only known charges enter an observed subtotal, and complete cost evidence requires every component and its total to be known. Missing files yield incomplete evidence; corrupt or conflicting content yields integrity errors. Origin is one of scripted reference, private lab export or external self-attestation. Hashes prove internal consistency, not authorship or truth.

Artifact paths are relative POSIX paths. Files are opened with descriptor-relative no-follow operations; components, sizes, regular-file status, post-read metadata and hashes are checked. Import copies only declared verified artifacts into an atomic new output. Unlisted files are ignored and never executed or copied. Outputs use private directory/file modes where supported. There is no archive import.

Bounds: 100 MiB retained artifacts/run, 50 MiB/WAV, 16 MiB/event stream, 10,000 events, 16 KiB/event, 100 artifacts, 128 selection entries, 90 seconds/audio. Limits are constants; no override interface is shipped. A single canonical run is read at a time during comparison; PCM is never kept for the entire cohort.

Event sequence strictly increases and clock offsets never decrease. Requests and responses share operation and call IDs. A network redelivery preserves both IDs and arguments; another agent decision has a new pair, even with a repeated idempotency key. Changed repeated-delivery identities fail integrity. Requests, attempts, permissions, snapshot objects and commit receipts are cross-checked. Every mutation attempt remains visible. Missing continuity cannot pass a dependent assertion.

The mandatory assertion registry comes from the installed seven-case policy, independent of imported fixture assertions. Deleting or changing required assertions fails validation. Positive booking checks use actual create arguments, authorized exact slots and returned IDs; null legacy fields remain unknown. The public sandbox requires nonempty name/service intake and a completed exact scripted turn before harness permission is accepted. This marker is not a production consent classifier.

## Initial draft clarifications

The supplied specification schema was a draft. Before the initial 0.1.0 implementation freeze, the registry was made expressive enough to encode the specified behavior:

- Status reads can return a denied/failed response with a code.
- Legacy exports explicitly mark `audit_completeness: "legacy_incomplete"` and may carry unavailable absolute reservation timestamps and commit revisions as null. Non-legacy evidence with missing revisions is rejected or incomplete; these exceptions never grant a pass.
- Canonical WAV measurement lineage has a closed `measurement` document: method ID, source audio hash, declared channel layout, alignment error and alignment source. No alignment is guessed.
- Comparison rows retain metric deltas and add typed per-arm counts, cost completeness and timing distributions. A closed suite manifest freezes all seven fixture hashes. Results bind the actual evaluating code, installed policy and requested scope so reevaluation can compare both arms under one current evaluator. Verified optional channel derivatives carry explicit source/hash lineage and must match the original PCM samples.

These are initial schema design decisions, not migration of a previously released semantic contract. Changes after release require a new contract version and reevaluation of both comparison arms.

## Reviews

Templates contain no scores, no completion time and unknown verdicts. Complete reviews cite retained artifact IDs and optional event IDs, the exact manifest hash, UTC completion time and reviewer identity. Example reviews never satisfy gates. Draft and partially filled reviews remain pending. A stale binding is invalid. A statement citation must name its events artifact and an assistant speech event; state-only citations cannot clear truthfulness. Audio-mode truthfulness and listening additionally require a citation to a retained, readable original canonical PCM audio artifact (16kHz stereo signed 16-bit WAV, at most 90 seconds). Scripted transcripts cannot establish observed speech in real-agent runs. Two distinct complete human reviewers with original media are required for listening readiness. Missing evidence remains unknown; explicit human failures remain blocking. Critical disagreement remains blocking until a later third distinct human explicitly adjudicates it with `resolves_review_sha256`, citing at least two contradictory complete review hashes, evidence and notes. All original reviews/hashes remain retained; recency and averages alone never resolve disagreement. Reviewer identities are not authenticated.
