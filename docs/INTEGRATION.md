# External harness integration

Install the package in your own harness environment. The CLI imports a directory; it never discovers, executes, isolates or networks your harness. `examples/conformance_writer.py` is an explicit, separate Python program for a local deterministic example, not a provider adapter.

1. Select one installed fixture and a fresh run/journey ID. Create a dedicated SQLite sandbox under a private directory with `Sandbox(path).create_run(run_id, journey_id, scenario)`.
2. Keep the run handle and independent audit interface inside the harness. Give the external agent a wrapper around only `handle.execute(capability, operation_id, request)`. The request is one of the four closed tool schemas. Do not expose the capability to prompts or export it.
3. Supply `agent_context(scenario)` and one caller turn at a time. Record the real turn's execution; call `record_permission` only for its completed exact script when the fixture grants it. Future/hypothetical/quoted text cannot grant permission.
4. Use actual returned IDs. Preserve call/operation/key on network redelivery. Record a new pair for a new decision. Never retry an uncertain mutation automatically: use `get_booking_status` to read the original reservation.
5. Close the capability on completion or interruption. Snapshot state and the complete audit independently. Preserve pending operations if interrupted. Use `Sandbox.open_existing(path).audit_run(run_id)` to inspect retained state after a crash; this cannot dispatch.
6. Write a sanitized configuration, exact scenario snapshot, events JSONL and state. Match the closed manifest contract. Hash every artifact byte, and hash scenario/configuration canonical JSON for their identities. Supply explicit software, adapter, condition/media/seed and fault implementation identities. For your agent, use execution mode `text` or `audio`, configuration agent kind `external`, and evidence origin `external_self_attested`.
7. Supply original local WAV and a measurement document only when channel layout and shared-clock alignment are known. Preserve the original hash; independently hash any derivative. Missing media does not permit downgrading an audio run to text. Media normalization and provider transport are outside this toolkit.
8. Run `validate`, `import` and `evaluate`. Generate and fill review sidecars for actual speech, including earlier unsupported claims. Do not fill observed intake or permission gaps from fixture expectations.

The current executable reference writer illustrates the bundle protocol end-to-end. Adapters must implement their own event capture and comparison identity discipline. Provider-specific compatibility is intentionally deferred until demonstrated use.

## Export captured snapshots with Python

`write_external_bundle` assembles the manifest and hashes from captured documents. It writes a new private output directory and reuses the importer’s cross-file checks before making that directory available. It never dispatches an agent or tool, changes a capability, repairs an audit, generates reviews, or evaluates the run. Stop new dispatch, await in-flight work, and close your sandbox capability before taking the final independent snapshots. After a crash, an audit-only handle can supply the retained snapshots without reopening dispatch.

```python
from smb_voice_bench.bundle_writer import write_external_bundle
from smb_voice_bench.reference_agents import implementation_identity

# These values come from your harness and actual capture; no fixture expectations
# or reference-run output may stand in for observed state, events or metadata.
manifest = write_external_bundle(
    destination,
    scenario=selected_scenario,
    configuration=sanitized_configuration,
    state=audit.snapshot(),
    events=audit.events(),
    execution_mode=captured_mode,          # "text" or "audio"
    conditions=sanitized_capture_conditions,
    sandbox_sha256=implementation_identity("sandbox"),
    started_at=captured_start_utc,
    ended_at=captured_end_utc,             # None when unavailable
    completion=captured_completion,
    seed=captured_seed,
    cost=observed_cost,                   # omit for unknown, never assumed free
    audio=original_wav_bytes,             # omit if unavailable; never convert here
    measurement=captured_measurement,     # omit if alignment is unavailable
)
```

The `sandbox_sha256` example above applies when the capture actually used this installed SQLite sandbox. An alternative fault/sandbox implementation needs its own exact implementation digest. Conditions must be explicit, sanitized, nonempty JSON; their snapshot is retained in the manifest’s `bench:conditions` extension and hashed for comparison. The writer’s code identity is retained separately. Include actual agent/adapter software revisions in the configuration parameters. Hashes and external origin remain self-attested; they do not authenticate an adapter or a reviewer.

Configuration must use `agent_kind: "external"`. The scenario must match one of the seven installed frozen fixtures exactly. Explicit reference configuration, reference-mode source events and `scripted_reference` speech are rejected rather than relabeled. The existing conformance example stays a clearly labeled scripted reference; unit-test toy captures of this writer are not provider observations.

Original audio bytes, if supplied, are retained unchanged as `original.wav`; no normalization or codec conversion occurs. A supplied measurement must bind that exact original hash. Missing audio preserves `execution_mode: "audio"` and remains insufficient evidence. Unknown end times and partial cost components also stay unknown. A completed run with no end time cannot clear functional evidence checks. An inconsistent capture leaves an `.incomplete-smb-*` staging directory for inspection; an existing destination or symlink is refused. The SQLite database and its dispatch capability are never included.

After export, use the ordinary `validate`, `import`, `evaluate`, `review-template` and `report` commands. Export success means the captured bundle was written consistently; it does not mean the agent passed.
