# Contributing

Thanks for helping grow the SMB receptionist benchmark. New scenarios and new
verticals are welcome. Two rules are non-negotiable, and CI enforces both.

## 1. Synthetic data only

Every scenario, fixture, default, and docstring **must use hand-authored,
fictional data**. Never paste real call transcripts, real customer records, or
real personal data of any kind. Use the reserved placeholder ranges:

- **Phone numbers:** the fictional NANP range — exchange `555`, line
  `0100`–`0199` (e.g. `(555) 555-0142`, `+1 800 555-0188`).
- **Emails:** reserved example domains — `example.com`, `example.org`,
  `example.net`.
- **Names / businesses / addresses:** obviously fictional.

Do **not** reference internal database column names, table names, tenant
identifiers, or per-customer field prefixes from any product. Name fields the way
an outside developer would.

A zero-dependency PII guard backstops this:

```bash
npm run lint:no-pii
```

It flags phone-shaped strings outside the reserved range, emails on non-reserved
domains, and UUID-shaped identifiers, and exits non-zero on any hit. (The
well-known payment test card `4111 1111 1111 1111` is the one allowlisted value,
used only by the sensitive-data safety fixture.)

## 2. No runtime-specific naming (no-runtime-leak)

This benchmark is runtime-neutral on purpose. Do **not** name a specific voice
runtime, backend platform, or CRM as "the" provider anywhere outside the
`adapters/` directory. In scenarios and docs, write **"the voice agent"** /
**"the agent-under-test"** — never a brand name. The only place a specific
harness/runtime may appear is inside `adapters/`, where each is listed as one
peer among equals (alphabetical, equal billing).

A zero-dependency guard enforces this:

```bash
npm run lint:no-leak
```

It greps every shipped file for forbidden tokens (runtime brand names, internal
column prefixes, CRM adapter keys, backend platform names, internal infra hosts).
Brand-name rules relax inside `adapters/`; database / infra / id rules are
enforced everywhere with no exception. Run the full check before opening a PR:

```bash
npm run check     # lint:no-leak + lint:no-pii + tests
```

## Adding a scenario

1. Create `scenarios/<vertical>/<slug>.json`. Set `schemaVersion` to
   `"smb-voice-bench/v1"` and `id` to `smbvb.<vertical>.<slug>` (the id's vertical
   segment must equal the `vertical` field).
2. Provide a synthetic `business_context`, a `script` with at least one
   `agent` turn marked `judged: true`, at least one `expected_intake_fields`
   entry, at least one `success_criteria`, and at least one `failure_traps`
   entry whose `mode` is one of the six canonical modes.
3. For safety scenarios, set `severity: "critical"` (blocking) and tag
   `check_tags` with `guardrails` and/or `escalation`.
4. Reference shared intake property names in `expected_intake_fields[].field`
   (`contact.name`, `contact.phone`, `service_type`, `party_size`, …) and set
   `intake_schema` to the matching outcome schema where applicable.
5. Run `npm run check`. The validator auto-discovers every JSON file under
   `scenarios/`; the coverage test ensures all six modes and all verticals keep
   at least one fixture.

## Adding a *new* vertical

`vertical` is a **closed enum** in
[`schema/scenario.schema.json`](schema/scenario.schema.json) (currently:
`event_rentals`, `home_services`, `restaurants`, `med_spas`,
`dental_medical_intake`, `legal_intake`, `quote_requests`, `booking_changes`,
`universal`). A fixture with a brand-new `vertical` value will **fail schema
validation** until the enum is extended. To add one:

1. Add the new value to the `vertical` enum in `schema/scenario.schema.json`
   (keep it lowercase `snake_case`).
2. Create `scenarios/<new_vertical>/` and add at least one fixture following
   "Adding a scenario" above (the `id` namespace must match: `smbvb.<new_vertical>.<slug>`).
3. Add a row to the **Coverage** table in [`README.md`](README.md).
4. Run `npm run check` — the coverage test requires every enum vertical to have
   at least one fixture, so a new vertical with no fixtures will fail.

## Authoring style

- Author from **patterns**, never from a transcript. If you would not be
  comfortable publishing it as obviously fictional, do not submit it.
- Embed noise / interruption / self-correction inside `caller` turns using the
  bracketed conventions (`[TV: "..."]`, `[silence]`, `— no wait, actually —`).
- Write `success_criteria` and `failure_traps` as independently checkable
  assertions so different judges agree as often as possible.
- Keep `notes` honest about provenance ("synthetic; authored from the common
  after-hours plumbing pattern").
