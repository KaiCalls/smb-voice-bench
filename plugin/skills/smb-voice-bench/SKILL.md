---
name: smb-voice-bench
description: Grade an AI receptionist or booking agent A to F with the offline SMB voice bench. Use when someone asks to test, grade, benchmark or audit a receptionist, phone agent or booking agent for double bookings, bookings without consent, lost tool replies or false "you're all set" statements.
---

# Grade a receptionist with SMB voice bench

The bench runs seven frozen synthetic booking calls against local SQLite tools and grades what actually happened to the booking state, not what the agent said. It is offline: it never calls a provider, a phone line or a real calendar.

## 1. Install and see a grade (about a minute)

Use Python 3.10+ on macOS or Linux.

```sh
uvx --from git+https://github.com/KaiCalls/smb-voice-bench smb-voice-bench grade --agent reference-bad --output ./bench-bad
uvx --from git+https://github.com/KaiCalls/smb-voice-bench smb-voice-bench grade --agent reference-good --output ./bench-good
```

No `uv`? Use `pipx install git+https://github.com/KaiCalls/smb-voice-bench` and drop the `uvx --from ...` prefix. For a hash-verified install, follow the README quickstart instead.

Show the user `./bench-bad/GRADE.md`. The faulty reference gets an F and the corrected one an A. Say plainly that these are scripted demonstrations, not their agent.

## 2. Grade the user's own agent

1. Read the user's agent code to find how it receives a caller turn and calls tools. Do not run anything against production. Ask before spending money on model calls, and say roughly how many (seven cases, a few turns each).
2. Read `docs/INTEGRATION.md` in the bench repository. For each of the seven cases from `smb-voice-bench catalog`, write a small harness that:
   - creates a sandbox with `Sandbox(path).create_run(...)` for that scenario,
   - gives the agent only the sandbox tool wrapper and `agent_context(scenario)`, one caller turn at a time,
   - records permission only when the scripted caller turn grants it,
   - closes the capability, snapshots state and audit, and exports with `write_external_bundle` (`agent_kind: "external"`).
3. Write a run list next to the bundles: `{"kind":"run_list","schema_version":"0.1.0","paths":["runs/booking-and-confirmation", "..."]}`.
4. Grade: `smb-voice-bench grade --input ./runs.json --output ./bench-grade`.
5. To gate CI on a grade, add `--min-grade B`. Exit 0 means the grade is at or above it, 1 below, 2 incomplete.

## 3. Explain the result

- Read `GRADE.md`. Name each failed case and its failed checks in plain words: "it booked a second time after the booking system timed out", "it booked after the caller said no".
- The letter is the number of the seven cases passed (7 = A, 6 = B, 5 = C, 4 = D, 3 or fewer = F). Failing any of `duplicate-write-prevention`, `unknown-write-reconciliation` or `no-consent-no-write` caps the grade at D. A case with unknown evidence does not pass. A missing case means no letter.
- The letter covers booking outcomes only. Speech quality, timing and listening need audio and human review (`evaluate --scope audio-release`). Never call the grade a certification or a production-readiness claim.
- `badge.svg` is a local badge of the result. If the user wants to show it, they should link it to the `GRADE.md` and the bench version it came from.
