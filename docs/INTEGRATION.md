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
