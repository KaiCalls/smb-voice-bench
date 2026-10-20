# Standalone toolkit migration

This draft keeps the Git history of `KaiCalls/smb-voice-bench` and proposes a Python offline booking-outcome toolkit at the repository root. The original JavaScript fixture pack is retained, byte for byte, under `legacy/fixture-pack-v1/` from commit `a5be8a6088af83fdde69ab253b89292557f7f0cb`. `SNAPSHOT.json` records the 57 original file hashes. `python tools/check_public.py` verifies that snapshot and the active source inventory.

The JavaScript package `@kaicalls/smb-voice-bench` version 1.0.0 and the proposed Python distribution `smb-voice-bench` version 0.1.0 are separate package ecosystems with incompatible contracts. Moving the old files changes repository-relative paths; existing consumers can pin the original commit. No npm or Python package publication is part of this migration. A root `npm test` no longer selects the old runner. Historical instructions are preserved in its own README and refer to that directory.

The old pack has 25 broad intake fixtures; the new toolkit has seven focused booking and recovery scenarios. These counts and scores must stay separate. The Python toolkit does not ingest old fixture JSON automatically or carry over old judge scores. New evidence needs its explicit manifest, audit, state and event contracts. Optional historical adapters and LLM judge code remain historical code and are never imported, executed or bundled by the Python CLI.

Both source families use MIT; their notices are retained. The Python wheel and source distribution include only active allowlisted toolkit files. The historical directory, local outputs, media, customer data, provider transports and private integration bridge are excluded from those archives. The source repository retains the historical snapshot for inspection.

This is a draft migration for review. Independent-person quickstart review and a separate release decision remain pending. Reference traces and synthetic PCM unit fixtures establish software behavior only; they cannot establish real speech quality or production readiness.
