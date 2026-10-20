# Provenance and dependency inventory

New package code, viewer, documentation, schemas and synthetic fixtures are offered under the MIT license in LICENSE. The seven fictional scripts and original contract draft originate in the supplied October 19, 2026 build specification and its synthetic supporting materials. The implementation is newly authored from that specification; private live workers, production prompts/rules, provider transports and customer-derived data are not copied into this package. Audio, remote fonts and third-party visual assets are not bundled.

The original KaiCalls MIT fixture pack is retained under `legacy/fixture-pack-v1/` with its original license and a hash snapshot; it is excluded from the Python distributions. See docs/MIGRATION.md for format and version differences.

Runtime dependencies are installed separately, not vendored. Exact resolved versions and artifact hashes are recorded in requirements.lock; retain upstream notices when redistributing dependencies:

| Dependency | Locked version | Upstream license |
| --- | --- | --- |
| jsonschema | 4.25.1 | MIT |
| attrs | 25.3.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| referencing | 0.36.2 | MIT |
| rpds-py | 0.27.1 | MIT |
| typing-extensions | 4.15.0 | PSF-2.0 |

Python and its standard library remain under the Python Software Foundation license. Development builds use the separately hash-locked requirements-dev.lock: setuptools 80.9.0 (MIT), build 1.6.1 (MIT), pyproject-hooks 1.3.3 (MIT), packaging 26.3 (Apache-2.0 OR BSD-2-Clause), and tomli 2.5.0 (MIT). These are not runtime imports. Browser verification tooling is development-only and excluded from the package.

License expressions above were checked against the hash-locked installed distribution metadata on October 19, 2026; repeat that check when dependencies change. Extraction does not automatically license unrelated private code. The public allowlist and package archive inventory are necessary review evidence, not proof that an arbitrary customer-derived corpus has been anonymized; this package avoids such a corpus entirely.
