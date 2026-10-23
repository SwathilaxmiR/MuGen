# Architecture

```
            ┌────────────┐  POST/GET   ┌───────────────┐  SQL (jobs, idempotency, queue)  ┌──────────┐
 client ───►│    api     │────────────►│   postgres    │◄─────────────────────────────────│  worker  │
            │  FastAPI   │             └───────────────┘   claim via SKIP LOCKED           │ pipeline │
            └─────┬──────┘                                                                 └────┬─────┘
                  │ presigned URLs / uploads                                                    │ put objects
                  └──────────────────────────► minio (S3) ◄─────────────────────────────────────┘
```

## Inside one job (worker child process, killable on `JOB_TIMEOUT_S`)

```
prompt ─► safety filters (named works, vocals) ─► interpreter (rules | llm | mock) ─► PromptSpec
PromptSpec + request ─► planner: key, tempo, N bars, hit time T, sections (snap/merge/drop), chord per bar ─► plan.json
plan ─► composer registry: drums | bass | harmony | melody  (deterministic RNG per stem seed)
each stem ─► MIDI ─► fluidsynth subprocess (reverb/chorus off)  ──fail x2──►  numpy synth  ──fail──► RENDER_FAILED
          └► riser FX ─► per-stem HP/EQ/Schroeder reverb/pan ─► (loop: keep 2nd pass) ─► exactly round(D·sr) samples
stems ─► shared ending envelope ─► per-stem balance ─► Σ ─► master gain ─► limiter curve from the sum ─► × every stem
      ─► 24-bit WAV + mp3 ─► QA gate (read back from files; one retry with −0.5 dB ceiling) ─► MIX_QA_FAILED or OK
mix + narration ─► VAD ─► gain curve (100 Hz grid) ─► mix_ducked.wav
everything ─► S3 jobs/<id>/ ─► music_manifest.json (validated) ─► status succeeded ─► signed callback
```

| Component | Responsibility |
|---|---|
| `api` | Validation, bearer auth, rate limit, correlation ID, idempotency, enqueue (202), status with presigned links, regenerate, uploads, health/ready, OpenAPI. Never touches audio. |
| `worker` | Claims jobs (`FOR UPDATE SKIP LOCKED`), runs each in a child process, heart-beats, enforces timeout, re-queues stale or transient failures up to `MAX_ATTEMPTS`, uploads, sends signed callbacks. |
| `interpreter` | Prompt → PromptSpec (style, valence, energy, mode, hints, flags). |
| `planner` | Pure functions: grid, sections, chords. |
| `composer` | Note lists per stem, behind a registry. |
| `renderer` | fluidsynth / numpy / mock adapters + per-stem FX. |
| `mixdown`, `qa`, `ducking`, `manifest`, `storage`, `db`, `cli` | As named. The QA functions are shared by the runtime gate, the tests and the batch runner. |
