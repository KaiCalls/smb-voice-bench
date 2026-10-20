# Proposed v0.1.0 release — not published

Source: `KaiCalls/smb-voice-bench`. This standalone draft preserves the historical fixture pack and proposes the Python toolkit at the repository root. Repository review does not publish a package or approve a release. The private integration bridge is excluded from this repository.

## Review gates

- Seven frozen synthetic cases; good controls pass and deliberately bad controls fail, including prevented duplicate/unauthorized decisions.
- Narrow contract, sandbox, evidence, review/audio, comparison and CLI tests; no provider test or broad monorepo build.
- Wheel installed in a fresh environment outside the source tree; catalog, demo, validation, evaluation and report work.
- Chromium and Firefox at 375px/1280px, direct file and loopback; keyboard/focus, no remote assets, inert hostile transcript, pagination and actual audio seek checked.
- Public file allowlist, filename/content/metadata/archive scan, MIT choice and dependency license metadata reviewed. Audio/private evidence never enters the extraction.
- Release archives have reproducible checksums. Signing remains a release action; no signing identity is fabricated.
- **An independent person must complete the quickstart before package readiness is declared.** Automated clean-install checks do not satisfy this human gate.

The release artifact directory contains a reference-only local demo, owner and technical screenshots, a 60–90 second screen recording and verification receipts. The video is a browser walkthrough of scripted text/tool evidence, not a live voice test. These development artifacts are separate from the public package allowlist and exclude private recordings.

## Local review commands

```sh
python -m unittest discover -s tests -v
python -m build --no-isolation --outdir /absolute/path/to/reviewed-distributions
python tools/check_public.py --dist /absolute/path/to/reviewed-distributions
```

Build with the locked runtime dependencies and the pinned build backend. Inspect both wheel and source archive before extracting allowlisted source to the intended destination. Existing hosting remains unchanged; the static report can open directly from disk. No ChatGPT Site is used.

Publication commands and signing must be prepared against the final approved destination and credentials during the separate release action. This package has no publish/deploy command. Three external teams using it more than once is a future adoption check, not an achieved result or a prerequisite falsely claimed here.

## Proposed announcement (draft only)

**KaiCalls releases open-source tests for whether AI receptionists complete the work they promise.**

SMB voice bench checks booking, correction and recovery behavior against a fictional business sandbox and independent evidence. Its local demonstration shows an uncertain response after a committed booking: the faulty reference tries creation twice, while the corrected reference verifies the original booking. A guard prevents duplicate records, and the second decision still fails.

The initial package covers seven synthetic cases, safe local evidence import, human-review sidecars, explicit comparisons and local reports. The included demo is scripted text and tools with no voice recording. Provider behavior, real speech quality, delivery and production readiness require separate evidence. Synthetic passes make no claim about customer growth or revenue.

## Proposed 75-second screen recording

0–12s: show the local report and its scripted/reference/audio-unavailable labels. 12–28s: show baseline/candidate counts and the insufficient release assessment. 28–48s: inspect the faulty reference, one committed booking and two create decisions; expand the denied attempt. 48–65s: inspect the corrected status read before one confirmation. 65–75s: show separate unknown speech/listening/repeatability dimensions and the export links. Do not describe the prevented duplicate as two actual bookings.

## Outreach draft (not sent)

We are preparing an offline benchmark for synthetic AI receptionist booking/recovery workflows. Would your team try the local quickstart and share whether the evidence helped reproduce a meaningful failure? We are looking for repeated practical use, not a provider ranking. All recordings and integration credentials stay in your environment.

## Reproduce viewer checks

With an optional development-only Playwright installation and its browsers, generate fixtures with `PYTHONPATH=src python tools/make_viewer_fixtures.py --output /absolute/new/fixture-directory`. Then run `node tools/browser_qa.cjs REPORT_DIRECTORY ARTIFACT_DIRECTORY FIXTURE_DIRECTORY PLAYWRIGHT_MODULE FIREFOX_EXECUTABLE CHROME_EXECUTABLE`. All paths are explicit; this development tool starts and closes a temporary loopback-only static server. It checks both browsers sequentially and writes screenshots plus a JSON receipt. The generated PCM is a synthetic test tone, never a speech-quality sample. Browser dependencies are not part of the runtime wheel.
