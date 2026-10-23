# Sources and licences

Every component that ships in the service image or touches generated audio is listed here, with the licence text that was read. `licenses.yaml` holds the same data in machine-readable form and feeds `components[]` in every `music_manifest.json`.

The default path contains **no trained generative model**. The music comes from rules and templates written for this repository (`src/musicengine/composer`, `styles/*.yaml`) and is rendered with a permissively licensed SoundFont. No song, artist or dataset was used to build it, and prompts that name works are stripped (`NAMED_WORK_IGNORED`).

## Audio path

| Component | Version | Licence | Evidence and clause | How it is used |
|---|---|---|---|---|
| **FluidR3_GM SoundFont** (Frank Wen, 2000-2002, 2008; Toby Smithe 2008) | Debian `fluid-soundfont-gm` 3.1-5.3; `.deb` SHA-256 `6f531493…fc60e`, `.sf2` SHA-256 `74594e8f…1bc1cb0`, both checked at image build | **MIT** | [Debian copyright file](https://metadata.ftp-master.debian.org/changelogs/main/f/fluid-soundfont/unstable_copyright): *"Permission is hereby granted, free of charge, … to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies…"* | Instrument samples for the default renderer. The rendered audio is new output; the SoundFont itself is not redistributed in the deliverables. |
| **FluidSynth** | Debian bookworm package (2.3.x in the image; 2.6.1 used in host tests) | **LGPL-2.1-or-later** | [Debian copyright](https://metadata.ftp-master.debian.org/changelogs/main/f/fluidsynth/stable_copyright): `Files: * … License: LGPL-2.1+` | Unmodified binary run as a **separate process** (`subprocess`, fast-render mode, reverb and chorus off); no linking. |
| **FFmpeg** (incl. libmp3lame) | Debian bookworm package (5.1.x); FFmpeg 9 in host tests | **GPL-2.0-or-later** for the Debian build | [Debian `rules`](https://salsa.debian.org/multimedia-team/ffmpeg/-/raw/debian/7%255.1.6-0+deb12u1/debian/rules): *"Most possible features, compatible with effective licensing of GPLv2+"* → `--enable-gpl`, no `--enable-nonfree` | Unmodified binary run as a **separate process** for mp3 encoding, narration decoding and the independent `ebur128` loudness cross-check. GPL terms apply when the binary is redistributed (the Debian source offer); they do not apply to the audio it produces. |
| **This repository** (composition rules, presets, numpy synth, Schroeder reverb, limiter, QA, ducking) | 0.1.0 | Owned code | - | Everything that decides the music. |

## Python libraries (installed from PyPI, unmodified)

Licence fields were read from each installed package's metadata (`importlib.metadata`); where metadata and the LICENSE file disagree, the LICENSE file wins.

| Package | Licence | Link |
|---|---|---|
| numpy | BSD-3-Clause | https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| scipy | BSD-3-Clause | https://github.com/scipy/scipy/blob/main/LICENSE.txt |
| soundfile (bundles libsndfile, LGPL-2.1, dynamically loaded) | BSD-3-Clause | https://github.com/bastibe/python-soundfile/blob/master/LICENSE |
| pyloudnorm | MIT | https://github.com/csteinmetz1/pyloudnorm/blob/master/LICENSE |
| pretty_midi, mido | MIT | https://github.com/craffel/pretty-midi/blob/main/LICENSE.txt |
| langdetect | Apache-2.0 (LICENSE file; the PyPI metadata field says "MIT", the classifier says Apache) | https://github.com/Mimino666/langdetect/blob/master/LICENSE |
| fastapi, starlette, uvicorn | MIT, BSD-3-Clause, BSD-3-Clause | https://github.com/fastapi/fastapi/blob/master/LICENSE |
| pydantic, pydantic-settings | MIT | https://github.com/pydantic/pydantic/blob/main/LICENSE |
| psycopg, psycopg-pool | LGPL-3.0-only (used unmodified as an installed library) | https://github.com/psycopg/psycopg/blob/master/LICENSE.txt |
| boto3 / botocore | Apache-2.0 | https://github.com/boto/boto3/blob/develop/LICENSE |
| httpx | BSD-3-Clause | https://github.com/encode/httpx/blob/master/LICENSE.md |
| structlog | MIT OR Apache-2.0 | https://github.com/hynek/structlog/blob/main/LICENSE-MIT |
| PyYAML | MIT | https://github.com/yaml/pyyaml/blob/main/LICENSE |
| python-multipart | Apache-2.0 | https://github.com/Kludex/python-multipart/blob/master/LICENSE.txt |
| pytest (tests only) | MIT | https://github.com/pytest-dev/pytest/blob/main/LICENSE |
| anthropic (optional `[llm]` extra, off by default) | MIT | https://github.com/anthropics/anthropic-sdk-python/blob/main/LICENSE |

## Infrastructure

| Component | Licence | Note |
|---|---|---|
| PostgreSQL 16 (`postgres:16-alpine`) | PostgreSQL License (permissive) | https://www.postgresql.org/about/licence/ |
| MinIO server `RELEASE.2025-04-22T22-12-26Z` | **AGPL-3.0** | https://github.com/minio/minio/blob/master/LICENSE. Used unmodified as a separate network service for compose and the demo. For production, set `S3_*` to a non-AGPL S3 backend (AWS S3, Cloudflare R2, …); no code change is needed. |
| Python 3.12 (`python:3.12-slim-bookworm`) | PSF License | https://docs.python.org/3/license.html |

## Evaluation-only components (not in the service image)

Listed in [eval/README.md](eval/README.md) with their licences when they are used. They score or compare outputs and are never part of the generation path.

## Optional LLM interpreter

`INTERPRETER=llm` sends the prompt text (after named-work and vocal filtering) to the Anthropic Messages API and gets back the same `PromptSpec` JSON. It is off by default, and no test or default code path needs a key. If it is enabled, the provider's commercial terms apply to that call. The music itself is still produced by the local symbolic engine.
