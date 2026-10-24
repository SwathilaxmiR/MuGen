# IncuBrix Music Engine (Assessment 1: AI background music)

Turns a text prompt into instrumental background music. Every request returns the full mix, four real stems (drums, bass, harmony, melody) and a `music_manifest.json`. Each output file is the exact requested length, the mix ends on a bar line, and loudness and true peak are measured and enforced. There is optional ducking under narration, a seamless loop mode, and you can regenerate a single stem.

**How it works.** The prompt is turned into a plan (style, tempo, key, bars, sections, chords). Each instrument part is composed from rules and rendered separately: MIDI goes through FluidSynth with the MIT-licensed FluidR3_GM SoundFont, then our own numpy effects are applied per stem. The mix is the exact sum of the stems. The default path uses no trained music model and no API keys, so there are no per-call fees.

```mermaid
flowchart LR
  C[client] -- POST /api/v1/music/jobs --> A[api<br/>FastAPI]
  A -- insert job + idempotency --> P[(postgres<br/>jobs = queue)]
  W[worker xN] -- SELECT ... FOR UPDATE SKIP LOCKED --> P
  W --> I[interpret prompt] --> PL[plan: tempo/key/bars/sections/chords]
  PL --> CO[compose 4 note lists] --> R[render each stem<br/>fluidsynth + numpy FX]
  R --> M[exact length, balance, master gain,<br/>one limiter curve for all stems]
  M --> Q[QA gate: length, LUFS, TP, sum, clicks, gaps, ending, sections]
  Q --> D[optional ducking under narration]
  D -- upload --> S[(MinIO / S3)]
  A -- presigned links --> C
  W -- signed callback --> C
```

ASCII version and component responsibilities are in [docs/diagram.md](docs/diagram.md).

## Setup (8 commands)

Needs Docker with Compose v2.24+. No API keys.

```bash
git clone <this repo> musicengine && cd musicengine
cp .env.example .env                       # optional: every setting has a default
make up                                    # builds the image (pins + checks the SoundFont SHA-256) and starts api, worker, postgres, minio
curl -s localhost:8000/ready               # {"status":"ready",...}
curl -s -X POST localhost:8000/api/v1/music/jobs -H 'Content-Type: application/json' \
  -d '{"prompt":"calm cinematic piano that builds to an uplifting peak","duration_s":45,"output":{"formats":["wav","mp3"]}}'
curl -s localhost:8000/api/v1/jobs/<job_id>   # poll until "succeeded"; result has presigned links
make test                                  # unit + integration + e2e inside compose
make batch                                 # every tests/inputs/*.json -> out/summary.csv, out/metrics.csv
```

> **Verification status:** the machine that built this repo had no Docker. The whole suite (`pytest tests`: 355 passed, 0 skipped) and the batch runner (48/48 cases) were run on the host instead, against native PostgreSQL 16, MinIO, FluidSynth 2.6.1 and FFmpeg 9 (see `scripts/dev_services.sh`). `Dockerfile`, `docker-compose.yml` and `make test` have **not** been run yet. Run `make up && make test` once on a Docker host before relying on them.

## Web UI

`web/` holds a React + TypeScript front end. In development, run `cd web && npm install && npm run dev` (http://localhost:5173, proxied to the API). Alternatively, `npm run build` and the API serves it at http://localhost:8000/. See [web/README.md](web/README.md). The Docker image does not build it yet.

## API

All routes are under `/api/v1`. `/health` and `/ready` sit at the root and are also aliased under `/api/v1`. The full contract is in [openapi.yaml](openapi.yaml), and a test fails if that file drifts from the running app.

| Route | What it does |
|---|---|
| `POST /api/v1/music/jobs` | Body: `prompt`, `duration_s` (5-300), optional `sections[] {start_s, mood}`, `tempo_bpm` (40-200), `key` ("C major", "F# minor", "Am"), `loopable`, `narration_url` (`https://`, `http://` or `upload://<id>`), `seed`, `output {sample_rate: 44100/48000, target_lufs: -30..-8, formats: ["wav","mp3"]}`, `callback_url`. Headers: `Idempotency-Key`, `X-Correlation-Id`, `Authorization: Bearer`. Returns **202** `{job_id, status, status_url}`. |
| `POST /api/v1/music/jobs/{id}/regenerate` | Body `{stem, seed?}`. The parent must have `succeeded`. Returns a new job (`parent_job_id` set). The other stems are copied byte for byte. |
| `GET /api/v1/jobs/{id}` | `{status: queued, running, succeeded or failed, progress 0-100, timestamps, warnings[], result {mix_wav, mix_mp3?, stems{}, mix_ducked?, manifest}, error?}` with presigned links. |
| `GET /api/v1/jobs/{id}/manifest` | The job's `music_manifest.json`, same-origin (used by the web UI). Returns 409 `PARENT_JOB_NOT_READY` until the job succeeds. |
| `POST /api/v1/uploads` | Multipart narration upload (up to `MAX_NARRATION_MB`). Returns `{url: "upload://<id>"}`. |
| `GET /health`, `GET /ready` | Liveness. Readiness checks the database, bucket, SoundFont, fluidsynth and ffmpeg. |

**Outputs** (in `s3://$S3_BUCKET/jobs/<job_id>/`):
- `mix.wav` (24-bit PCM, 48 kHz by default)
- `mix.mp3` (if requested)
- `stems/{drums,bass,harmony,melody}.wav`
- `mix_ducked.wav` (only with narration)
- `music_manifest.json`
- `plan.json` and `master.npz`, kept so a stem can be regenerated

**Callbacks.** When a job reaches a terminal state, the worker POSTs the status JSON with `X-IncuBrix-Signature: sha256=<hex HMAC-SHA256(raw body, CALLBACK_SECRET)>`. It retries 3 times with backoff (0.5 s, 1 s, 2 s). To verify, compute the HMAC over the raw body and compare in constant time.

**Idempotency.** Keys are scoped to (key, route). The same key with the same body returns the same job and the work is done once. The same key with a different body returns **409** `IDEMPOTENCY_KEY_REUSED`. Parallel identical requests also create exactly one job (tested with 8 threads).

### Error codes

Every error is JSON: `{"error": {"code", "message", "retryable", "details"}}`. This includes FastAPI validation errors, unknown routes and uncaught exceptions.

| Code | HTTP | Retryable | When |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | no | Bad body, parameters or JSON; unknown `upload://` id; bad `Idempotency-Key` |
| `UNAUTHORIZED` | 401 | no | `API_TOKEN` is set and the bearer token is missing or wrong |
| `RATE_LIMITED` | 429 | yes | More than `RATE_LIMIT_PER_MIN` writes (or 10× that many reads) per token or IP per minute; `Retry-After` header is set |
| `QUEUE_FULL` | 503 | yes | Queued + running jobs ≥ `MAX_QUEUE` |
| `JOB_NOT_FOUND` | 404 | no | Unknown or malformed job id |
| `IDEMPOTENCY_KEY_REUSED` | 409 | no | Same key, different body |
| `PARENT_JOB_NOT_READY` | 409 | yes | Regenerate requested before the parent succeeded |
| `STEM_NOT_FOUND` | 422 | no | Regenerate with an unknown stem |
| `PAYLOAD_TOO_LARGE` | 413 | no | Upload over `MAX_NARRATION_MB` |
| `NOT_FOUND` | 404 | no | Unknown route |
| `METHOD_NOT_ALLOWED` | 405 | no | Wrong method |
| `INTERNAL_ERROR` | 500 | yes | Unexpected server error |

These job-level failures appear in the `error` field of a `failed` job:

| Code | Retryable | When |
|---|---|---|
| `RENDER_FAILED` | yes | The primary renderer failed twice and the fallback renderer also failed |
| `JOB_TIMEOUT` | yes | Exceeded `JOB_TIMEOUT_S` (the job process is killed); re-queued until `MAX_ATTEMPTS` |
| `MIX_QA_FAILED` | yes | The QA gate failed even after one automatic retry with more headroom; `details` holds the metrics |
| `STORAGE_ERROR` | yes | Upload to S3 failed; re-queued until `MAX_ATTEMPTS` |
| `INTERNAL_ERROR` | yes | Crash, or a worker that stopped heart-beating more than `MAX_ATTEMPTS` times |

### Warning codes

Warnings appear in both the job status and the manifest, in the shape `{code, message, details?}`.

| Code | Meaning |
|---|---|
| `CONTRADICTORY_PROMPT` | Opposed energy words (e.g. "calm but aggressive"). Resolved to mid energy, minor mode, slow-to-mid tempo, percussive "tense" timbre unless a genre was named |
| `NAMED_WORK_IGNORED` | A song, artist or film reference ("in the style of X", "sounds like X", quoted titles, known names) was removed |
| `VOCALS_NOT_SUPPORTED` | A vocal request (sing, lyrics, rap, choir…) was removed; the output stays instrumental. "no vocals" does not warn |
| `PROMPT_TRANSLATED` | A non-English prompt was mapped with the built-in es/fr/de/pt/hi/ta/ja/zh lexicon (or translated by the LLM adapter) |
| `PROMPT_LANGUAGE_FALLBACK` | Non-English prompt with no lexicon match; neutral defaults were used |
| `VAGUE_PROMPT_DEFAULTS` | No mood or genre words; the neutral `corporate` preset was used at moderate energy |
| `SECTIONS_MERGED_MIN_GAP` | Two sections closer than `MIN_SECTION_GAP_S` after snapping; the earlier start was kept with the higher intensity |
| `SECTION_AFTER_END_DROPPED` | A section starts at or after one beat before the final hit |
| `SECTION_SNAPPED` | A section was moved to the nearest bar line (if within 0.5 s) or beat; `details.delta_s` |
| `TEMPO_ADJUSTED_FOR_LOOP` | A fixed tempo cannot fill a loop with whole bars, so the nearest tempo that can was used |
| `TEMPO_OUTSIDE_SNAP_RANGE` | Fixed tempo below 60 bpm: one beat is over 1 s, so a snap can exceed 0.5 s |
| `ENDING_ON_BEAT_NOT_BAR` | A very slow fixed tempo on a very short track: the final hit lands on a beat, not a bar line |
| `NARRATION_NO_SPEECH` | No speech detected; `mix_ducked.wav` equals the mix |
| `NARRATION_FETCH_FAILED` | Fetch, decode or SSRF guard failed; the job succeeds without `mix_ducked.wav` |
| `NARRATION_TRUNCATED` | Narration is longer than the music; speech after the end is ignored |
| `PROVIDER_FALLBACK_USED` | The primary renderer failed for a stem; the fallback renderer was used |
| `LLM_UNAVAILABLE_RULES_USED` | `INTERPRETER=llm` failed or is unconfigured; the rules interpreter was used |
| `LOOP_IGNORES_ENDING` | Loop mode: no final hit, and the file wraps seamlessly on a bar line |
| `REGEN_STEM_TRIMMED` | The regenerated stem was lowered to keep the mix true peak ≤ −1 dBTP |

## How the hard requirements are met

| Requirement | Mechanism | Measured (batch run 3, 48 cases, `testpack/run3/metrics.csv`) |
|---|---|---|
| Length ±0.05 s, ends on purpose | Tempo and bar count are planned so the final hit lands on a bar line, with a 0.75-2.5 s decaying tail. Every file is trimmed or padded to `round(D·sr)` samples. A squared raised-cosine fade runs after the hit | Length error **0 samples** in every file. QA requires the last 50 ms < −60 dBFS and an onset at the hit |
| ≥3 real stems that sum to the mix | Four stems, each rendered from its own MIDI part. Stems are stored after the master gain and the shared limiter curve, so `mix = Σ 1.0·stem` | Sum difference **−110.8 to −120.5 dB** |
| Instrumental only | No GM voice or choir programs (52-54, 85, 91 are rejected at preset load). Vocal words are stripped | `test_no_vocal_programs_anywhere` |
| Commercially safe | Owned code + MIT SoundFont + permissive libraries; fluidsynth and ffmpeg run as separate programs. Named works are stripped. See [SOURCES.md](SOURCES.md) | `components[]` in every manifest |
| 48 kHz WAV, −16 LUFS ±1, TP ≤ −1 dBTP | Iterative master gain plus a 4×-oversampled look-ahead limiter (ceiling −1.5 dBTP). The gate is ±0.5 LU, cross-checked with `ffmpeg ebur128` | LUFS within 0.3 LU of target; ffmpeg agrees within 0.1 LU. TP −1.60 dBTP worst (mp3 −1.40) |
| No clicks, clipping or gaps | The harmony is continuous across section changes; decaying instruments re-strike. QA runs click, gap and full-scale detectors | 0 clicks, 0 gaps, 0 full-scale samples |
| Sections on a beat within 0.5 s | Snap to the bar line if within 0.5 s, else to the nearest beat. Free tempo is ≥ 80 bpm. The composers change intensity exactly at the snapped beat | QA checks the onset or level step at every section |
| Ducking −8 to −15 dB, smooth | Energy VAD with hysteresis; gaps < 0.6 s bridged; −12 dB with a 120 ms raised-cosine attack before speech and a 500 ms release. The curve is in the manifest | Depth 12 ± 1 dB in tests; monotonic transitions |
| Regenerate one stem | Saved plan + new stem seed; the new stem is loudness-matched and the parent limiter curve applied | Other stems are byte-identical (SHA-256) |
| Seamless loop | `D = N·bar` exactly; the MIDI is rendered twice and the second pass kept | Seam click detector clean |

## Configuration

Every setting comes from the environment (see [.env.example](.env.example)).

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://music:music@localhost:5432/music` | Jobs, idempotency, queue |
| `S3_ENDPOINT` / `S3_PUBLIC_ENDPOINT` | `http://localhost:9000` | Internal endpoint / host used in presigned links |
| `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION` | `music`, `minioadmin`, `minioadmin`, `us-east-1` | Object storage (change the keys for any shared deployment) |
| `PRESIGN_TTL_S` | `86400` | Link lifetime |
| `API_TOKEN` | empty (auth off) | Bearer token required on `/api/v1/*` except health/ready |
| `RATE_LIMIT_PER_MIN` | `30` | Writes per token or IP per minute (reads get 10×) |
| `MAX_QUEUE` | `50` | Queued + running jobs before `QUEUE_FULL` |
| `WORKER_CONCURRENCY` | `2` | Worker processes per container |
| `JOB_TIMEOUT_S` / `MAX_ATTEMPTS` / `HEARTBEAT_STALE_S` / `POLL_INTERVAL_S` | `900` / `3` / `60` / `0.5` | Timeout kill, retries, stale re-queue, polling |
| `RENDERER` / `RENDERER_FALLBACK` | `fluidsynth` / `numpy` | `fluidsynth`, `numpy` (own synth) or `mock` (sine) |
| `FLUIDSYNTH_BIN` / `FLUIDSYNTH_TIMEOUT_S` / `SOUNDFONT_PATH` / `FFMPEG_BIN` | `fluidsynth` / `120` / `/opt/soundfonts/FluidR3_GM.sf2` / `ffmpeg` | Binaries |
| `INTERPRETER` | `rules` | `rules`, `llm` or `mock` |
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_TIMEOUT_S` | `anthropic` / `claude-opus-5-5` / empty / `15` | Optional LLM interpreter (needs `pip install -e ".[llm]"`) |
| `CALLBACK_SECRET` / `CALLBACK_TIMEOUT_S` | `change-me` / `5` | HMAC key for callbacks |
| `ALLOW_PRIVATE_URLS` | `false` | SSRF guard for `narration_url` / `callback_url` (blocks private, loopback, link-local and metadata IPs) |
| `MIN_SECTION_GAP_S`, `MIN_DURATION_S`, `MAX_DURATION_S` | `1.5`, `5`, `300` | Music rules |
| `TARGET_LUFS_DEFAULT`, `TP_CEILING_DBTP`, `LUFS_TOL` | `-16`, `-1.5`, `0.5` | Loudness targets |
| `DUCK_DB`, `DUCK_ATTACK_MS`, `DUCK_RELEASE_MS`, `DUCK_BRIDGE_GAP_S` | `12`, `120`, `500`, `0.6` | Ducking |
| `MAX_NARRATION_MB`, `NARRATION_FETCH_TIMEOUT_S` | `50`, `20` | Narration limits |
| `COST_PER_CPU_SECOND` | `0.0000134` | Cost model input ($/vCPU-second of your server) |
| `FAULT_INJECT` | empty | Test only: `render_primary_fail`, `render_timeout`, `llm_fail` |
| `WEB_DIST_DIR` | `<repo>/web/dist` if built | Built web UI served at `/` |
| `LOG_LEVEL` | `INFO` | structlog JSON logs (`timestamp, level, event, job_id, correlation_id`) |

## Tests

```bash
make test          # everything, inside compose (unit + integration against postgres/minio + e2e against api/worker)
make test-local    # host: unit tests; integration/e2e skip with a reason unless services are reachable
```

- `tests/unit`: time grid matrix (D ∈ {5, 5.5, 6, 10, 45, 180, 300} × tempo × loop), sections, interpreter (10 prompts, named works, vocals, contradiction, vague, es/hi/ta/ja/fr), composer (determinism, in-key, continuity, final hit), renderers and fallback, mixdown/QA over 12 presets at −14/−16/−23 LUFS, ducking, manifest, regenerate, loop.
- `tests/integration`: API contract (every error code, auth, rate limit, idempotency incl. 8 parallel requests, uploads, `openapi.yaml` drift), and the worker (lifecycle, progress, `SKIP LOCKED` claims, kill -9 mid-job → stale re-queue → success, timeout, signed callback with retry, correlation ID in logs). These use a separate `<db>_it` database.
- `tests/e2e`: the real renderer at 10 s and 60 s, regenerate, loop seam, same key twice, 4 concurrent jobs, and every `tests/inputs/hard_*.json`.

## Batch runner

```bash
python -m musicengine.cli batch --api http://localhost:8000 --token "$API_TOKEN" --input tests/inputs --out out/ [--run-id v3] [--only p0,hard_]
```

For each case, the runner:
1. Uploads synthetic narration if the case has it.
2. Submits with a deterministic `Idempotency-Key` (case name + body + `--run-id`).
3. Polls until the job finishes, then downloads the mix, stems, mp3, ducked mix and manifest.
4. Re-runs the QA gate locally and computes the bleed and spectral-overlap metrics.
5. Checks the case's expectations (status, warnings, regenerate byte-identity).

It writes `out/<case>/…`, `out/summary.csv` and `out/metrics.csv`. The `metrics.csv` columns are: generation seconds, seconds per 60 s, length error, LUFS (ours + ffmpeg), true peak (wav, ffmpeg, mp3), sum-diff dB, bleed per stem, cross-correlation, spectral overlap, clicks, gaps, compute seconds, $/min and warnings.

The prompt-match score (CLAP) is computed separately in `eval/` because it needs model weights that are not in the service image.

## Assumptions (where the brief is silent)

1. 4/4 time only, stereo output.
2. WAV is always produced; mp3 only on request. Sample rates are 44100 and 48000.
3. Stems are stored after the master gain and limiter; the manifest gains are 1.0, so `mix = Σ gain·stem` exactly.
4. LUFS is enforced at ±0.5 LU (the brief allows ±1); the true-peak ceiling is −1.5 dBTP (the brief allows −1).
5. Loop mode has no final hit by definition. "Ends on purpose" is met because the file ends exactly on a bar line and wraps. A fixed tempo may be adjusted so the loop fits whole bars (with a warning).
6. Narration starts at t = 0 of the video timeline. `mix_ducked.wav` is not re-normalised.
7. A narration fetch failure gives a successful job without `mix_ducked.wav`, plus a warning.
8. `Idempotency-Key` is optional and scoped to (key, route).
9. With no `sections`, a default arc is used (intro, then build at ≈30%, then peak at ≈65%, or a builds-to-climax arc when the prompt says so). Tracks under 8 s get one section.
10. Sections that start inside the final tail count as "after the end".
11. Realism is limited by the GM SoundFont. The goal is clearly different, recognisable genres, not studio realism.
12. The API runs as one process (in-memory rate limiter); scaling out needs a shared limiter.
13. Regenerate does not re-duck; send a new job with `narration_url` for that.

## Known limitations

- **Realism and prompt match:** GM SoundFont rendering is clearly less realistic than neural audio. Prompt match is judged by listening, and by CLAP in `eval/`.
- **Slow fixed tempos:** a fixed tempo below 60 bpm can put a section change more than 0.5 s from the request. This is warned (`TEMPO_OUTSIDE_SNAP_RANGE`), not hidden.
- **SSRF DNS rebinding:** the guard resolves and checks the host before fetching but does not pin the IP, so DNS rebinding between the check and the connect is not prevented.
- **MinIO licence:** MinIO is AGPL-3.0 and is only used as the compose / demo object store. Point the `S3_*` variables at another S3-compatible backend in production.

## Repository map

`src/musicengine/` contains `api/` (routes, middleware, idempotency), `worker/` (loop, pipeline, callbacks), `interpreter/` (rules, llm, mock, lexicons), `styles/` (12 presets), `planner/` (time grid, sections, plan), `composer/` (registry + one file per stem), `renderer/` (fluidsynth, numpy, mock, fx), `mixdown.py`, `qa.py`, `ducking.py`, `manifest.py`, `storage.py`, `db.py`, `cli.py`. `eval/` holds evaluation-only scripts (not in the service image). `testpack/` holds the batch results, including the failures from run 1.

Live-session hooks:
- **New stem type:** add a composer and register it in `composer/registry.py`, then add its program to the presets.
- **New manifest field:** `manifest.py`.
- **Minimum section gap:** `MIN_SECTION_GAP_S` and `planner/sections.py`.
