# Scenario schema

> **Disclaimer — not legal or safety advice.** These scenarios model behavioral
> coverage for testing an AI receptionist agent. They do not implement,
> guarantee, or replace any emergency-response, medical, legal, privacy, or
> consumer-protection obligation. Escalation behavior and any regulated handling
> are the integrator's responsibility.

A scenario is one JSON object validated by
[`schema/scenario.schema.json`](../schema/scenario.schema.json) (JSON Schema
Draft 2020-12). The shape is **independently versioned** via `schemaVersion` so
it can evolve without coupling to any other schema.

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schemaVersion` | const `"smb-voice-bench/v1"` | yes | Independent schema tag. |
| `id` | string | yes | Stable id, `smbvb.<vertical>.<slug>`. |
| `title` | string | yes | One-line summary. |
| `vertical` | enum | yes | `event_rentals`, `home_services`, `restaurants`, `med_spas`, `dental_medical_intake`, `legal_intake`, `quote_requests`, `booking_changes`, `universal`. |
| `caller_goal` | string | yes | What the caller is trying to accomplish. |
| `business_context` | object | yes | Synthetic operating context (`business_name`, `business_type`, `hours`, `services[]`, `booking_enabled`, `payments_enabled`, `transfer_enabled`, `location_hint`). |
| `intake_schema` | enum | no | Name of the shared intake outcome schema this call should produce. |
| `script` | array | yes | Ordered turns: `{ role: "caller" \| "agent", content?, judged? }`. Must contain ≥1 `agent` turn with `judged: true`. |
| `expected_intake_fields` | array | yes | `{ field, required, expected_value?, notes? }`. `field` references the shared intake vocabulary. ≥1 item. |
| `success_criteria` | string[] | yes | Positive, independently checkable conditions. ≥1. |
| `failure_traps` | array | yes | `{ id, mode, description }`. ≥1. `mode` is one of the six canonical modes. |
| `must_not_claim` | string[] | no | Quick-consume subset of traps. |
| `must_escalate_if` | string[] | no | Conditions requiring escalation / redirect. |
| `severity` | enum | no | `low \| medium \| high \| critical` (default `medium`). `critical` = blocking. |
| `check_tags` | enum[] | no | Rollup tags: `intake`, `truthfulness`, `guardrails`, `escalation`, `identity`, `behavior`, `robustness`. |
| `modality` | enum | no | `text` (default) \| `audio` (reserved for a future pack). |
| `notes` | string | no | Authoring rationale / provenance. |

## The script and judged turns

`caller` turns carry `content`. The final `agent` turn(s) marked `judged: true`
are graded against the rubric; intermediate scripted `agent` turns (with
`content`) only provide context. Noise, interruption, and self-correction
artifacts are embedded **inside** `caller` turns with bracketed conventions:

- `[TV: "...act now and save..."]` — a broadcast bleeding into the transcript
- `[other person, away from phone: "..."]` — crosstalk
- `[silence]` — dead air
- `— no wait, actually —` — a mid-sentence self-correction (barge-in modeled at
  the transcript level)

A judge must treat these as artifacts, not as caller intent.

## `expected_intake_fields` and the shared vocabulary

`field` values use property names from a shared intake vocabulary **defined here,
in this document** (there is no external package to install), so the same fixture
can assert structured extraction on any harness. `field` is a free-form string —
the names below are the recommended convention, not a closed set. Dotted paths
address the shared contact fragment:

- `contact.name`, `contact.first_name`, `contact.last_name`, `contact.email`,
  `contact.phone`, `contact.intent`, `contact.preferred_contact_method`

Outcome-specific fields use the matching `intake_schema`'s property names, e.g.
`service_type`, `service_address`, `problem_description`, `preferred_window`
(home-service-quote); `party_size`, `requested_slot`, `seating_preference`
(restaurant-reservation); `action`, `service`, `requested_slot`
(appointment-request); `items_requested`, `delivery_address`, `event`
(event-rental-lead); `reason_for_call`, `callback_window`
(missed-call-followup); `emergency_type`, `location` (emergency-escalation);
`lead_status`, `notes` (crm-handoff).

A `required: true` field that the agent fails to capture trips a `missing_intake`
failure.

## Validation

```bash
npm test            # validates every fixture against schema/scenario.schema.json
npm run check       # no-leak + no-pii guards + tests
```
