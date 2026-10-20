# v0.1 implementation acceptance

The offline implementation is complete within the seven-scenario scope. It installs independently, reproduces the reference failure/recovery, checks actual synthetic SQLite state, retains failures and unknowns, compares cohorts, and renders local evidence reports. External capture export and the separate private legacy bridge use the same installed contracts. This is software acceptance, not a package publication or a real-agent readiness claim.

| Work package | Acceptance evidence |
| --- | --- |
| Contracts and packaging | Closed local schemas, strict canonical JSON, safe bounded paths, locked dependencies, exact wheel/source inventories; Python 3.10 and 3.12 CI |
| Business sandbox | Real SQLite tests for durable unknown writes, permissions, ID ownership, idempotency, audit history, capability closure and concurrent redelivery |
| Seven scenarios and references | All seven good controls pass functional checks; all seven deliberately bad controls fail; a 70-trace matrix covers five repetitions per control |
| Import and evaluation | Missing/corrupt/interrupted controls; partial outcomes; nullable metadata; complete-script checks; evidence-bound reviews; conservative PCM alignment and media checks |
| Comparisons and reports | Disjoint explicit cohorts, incompatible/missing rows, critical failures, separate dimensions, counts/cost completeness, local JSON/plain/HTML exports |
| CLI and external capture | Every CLI command exercised from installed wheels outside the checkout; original import bytes retained; unfilled reviews stay unfilled; export never dispatches or grades |
| Private legacy bridge | Separate offline tests and retained-evidence export verify original hashes remain unchanged; legacy consent/intake/alignment omissions stay unknown; private data is excluded here |
| Release materials | MIT/provenance inventory, contribution/security guides, methods, draft announcement/outreach, screenshots and reference screen recording prepared; release gates below remain explicit |

## Reproduce the installed workflow

Build and install the reviewed wheel into a fresh environment using the README’s hash-locked dependencies. Change to a separate temporary directory, leave `PYTHONPATH` unset, and run:

```sh
python /absolute/checkout/tools/verify_install.py --output ./acceptance-report
```

The tool verifies the installed module is outside the source tree, then exercises doctor, catalog, demo, simulate, validate, import, evaluate, review-template, compare and report. It runs seven good/bad reference pairs, regenerates both report types, checks unknown audio-release evidence, and tests missing/corrupt copies and refused overwrite. An audit hook rejects socket activity and credential-file reads. The resulting `acceptance.json` records exact exits, interpreter, package size, elapsed time and peak memory. It creates no live/provider observation and assigns no human review scores.

The October 20 clean macOS runs used Python 3.10.19 and 3.12.12. Each full installed workflow took about eight seconds, with peak RSS below 43 MiB and no network or credential-file access. These are engineering observations, not portable performance guarantees. CI repeats the workflow against built wheels and runs the 56 focused tests sequentially on both interpreter targets.

The final viewer checks passed in Chromium and Firefox at 375px and 1280px, direct file and temporary loopback access. They covered keyboard/focus, no overflow, inert hostile text, 500-row pagination, original/verified-channel audio seeking, no autoplay, and no external asset requests or script errors. Synthetic PCM tones verify playback mechanics only.

## Release boundary

The code can be used from this repository or a locally built wheel now. The maintainer authorized v0.1.0 as an initial GitHub engineering release after automated acceptance. An independent-person quickstart has not been recorded; automated acceptance does not impersonate that person. Release assets include checksums and signed build provenance. PyPI distribution, announcements and outreach are separate actions. No real speech/listening or production-readiness claim follows from these reference checks.
