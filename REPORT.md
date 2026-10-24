# REPORT: IncuBrix Assessment 1, AI Background Music Engine

Every number below was produced by code in this repository; the file that holds it is linked. Hardware for all measurements: **Apple M5 (10-core) MacBook Air, fanless**, with native PostgreSQL 16, MinIO, FluidSynth 2.6.1 and FFmpeg 9. Docker was not available on this machine, so nothing here was measured inside containers.

## 1. Summary and recommendation

**Recommendation: ship Approach A (symbolic composition rendered per instrument) now. Revisit a hybrid later.**

Approach A meets every hard constraint by construction:
- exact length;
- a final hit on a bar line;
- stems that are genuinely separate parts and sum to the mix to within −111 dB;
- loudness and true peak enforced and cross-checked;
- regenerate-one-stem with the other stems byte-identical;
- seamless loops;
- no licence risk from model weights, and no per-call fees.

Its weakness is realism. GM-SoundFont rendering is expected to sound synthetic next to neural audio; that has not yet been judged by human listeners. Prompt match measured with CLAP is above chance but modest (§4). Approach B (text-to-music + source separation) did not beat A on CLAP on the same prompts (0.454 vs 0.508, n = 5) and was about 70× slower on CPU. Its stems are estimates that leak into each other, its length and ending are not controlled, and the open model we could test (MusicGen) is **licensed for non-commercial use only** (§6). A later hybrid could put a neural timbre or melody layer on top of A's exact grid, if a commercially licensed model is available.

## 2. What was built

Architecture (diagram in [docs/diagram.md](docs/diagram.md)):
- The `api` service (FastAPI) handles validation, auth, rate limits, idempotency, uploads and status.
- PostgreSQL holds the jobs and doubles as the queue (`FOR UPDATE SKIP LOCKED`).
- The `worker` runs each job in a killable child process with heartbeats, a timeout, stale re-queue and signed callbacks.
- MinIO / S3 stores the outputs.

The pipeline:
1. Safety filters (named works, vocals), then the rules interpreter, which uses 12 YAML style presets.
2. The planner (exact grid, section snapping and merging, chords).
3. Four deterministic composers behind a registry.
4. A FluidSynth subprocess per stem, with a numpy-synth fallback.
5. Per-stem FX.
6. Mastering: a shared ending envelope, per-stem balance, a master gain, and one look-ahead limiter curve computed from the sum and applied to every stem.
7. The QA gate.
8. Optional ducking.

Development followed tasks T0–T16, each with its own commit and tests. **352 tests pass**, with none skipped: unit, integration against real Postgres and S3, and e2e against a running API and worker with the real renderer.

## 3. Must-haves: measured

Batch run 3 covered 48 cases (`tests/inputs/*.json`): 12 style prompts, a duration matrix of 10/30/60/180 s, every §6 hard case, loops, regenerate, 44.1 kHz, −14 and −23 LUFS targets, and one validation error. **All 48 cases passed every check** ([testpack/run3/summary.csv](testpack/run3/summary.csv), [metrics.csv](testpack/run3/metrics.csv)).

| Must-have | Target | Measured over 47 generated outputs |
|---|---|---|
| Length, mix + every stem | ±0.05 s | **0 samples** error in every file |
| Ends on purpose | hit or fade on a bar line | Every non-loop output has an onset at the hit (spectral flux ≥ 2× median) and its last 50 ms is below −60 dBFS |
| Stems sum to the mix | Σ gain·stem = mix | **−110.8 to −120.6 dB** difference (24-bit rounding), all gains 1.0 |
| Loudness | target ±1 LU | Within **0.28 LU** of target (ours); ffmpeg `ebur128` agrees within **0.08 LU** |
| True peak | ≤ −1 dBTP | Worst **−1.60 dBTP** WAV (ffmpeg −1.6); worst **−1.40 dBTP** decoded mp3 |
| Clicks / gaps / clipping | none | 0 / 0 / 0 full-scale samples |
| Sections | on a beat, within 0.5 s | Snapped by construction; QA confirmed an onset or level step at every change |
| Instrumental | no vocals | No voice programs can be loaded; vocal prompts warned and stripped |

The ±0.5 LU and −1.5 dBTP internal targets are tighter than the brief (±1 LU, −1 dBTP) to leave headroom for mp3.

## 4. Prompt match (independent model)

Prompt match was scored with `laion/clap-htsat-unfused` (Apache-2.0) over 42 English-prompt outputs and 36 distinct prompts ([eval/results/clap.md](eval/results/clap.md)):

- **Matched** prompt cosine: mean **0.347** (sd 0.180).
- **Mismatched** control (the same audio against every other prompt): **0.265** (sd 0.048).
- Matched beats the control for **30 of 42** outputs. The metric discriminates, but not strongly.
- **Retrieval:** the audio's own prompt ranks first for 4/42 outputs and in the top 3 for 9/42 (chance top-1 is 0.03). Many prompts are near-duplicates (several "calm ambient…" or "corporate…" variants), which lowers rank-based scores.
- **Against the simple baseline** (one piano loop at a fixed tempo) on the 6 listening-test prompts, ours scores higher on **6/6**. Examples: cinematic 0.694 vs 0.180; tense 0.481 vs 0.112.

The first CLAP model tried (`laion/larger_clap_music`) produced identical embeddings for every text and was rejected (documented in [eval/README.md](eval/README.md)).

**Blind listening test: not run yet.** It needs ≥ 5 human listeners. The pack generator, protocol and results template are ready ([eval/listening_test.md](eval/listening_test.md)), and no preference numbers are claimed. Listening notes for T13 also need a human: the coding agent cannot hear the audio.

## 5. Stem cleanliness

Results are in [eval/results/bleed.md](eval/results/bleed.md), over 47 outputs.

- **Waveform cross-correlation** between stems: mean of the per-output maximum is **0.031**.
- **Spectral overlap:** each stem shares **0.71** of its spectrum with another stem, against **0.25** for a band-split control made from the same mix. Overlap is higher than the control in 46/47 outputs, which is evidence that the stems are played parts, not EQ bands.
- **Shared-content index** (the plan's "bleed" metric: an NNLS fit of each stem's STFT magnitude onto the other stems) is **−9.5 dB** mean. **It does not detect leakage.** The band-split control scores *lower* on it (more "clean"), because stems in the same key and rhythm share content by design. It is reported as defined, with this caveat, rather than presented as a bleed number.

Bleed is zero by construction, because each stem is rendered alone from its own note list. The sum difference above is the stronger evidence.

## 6. Approach B comparison

Same 5 prompts, 30 s each, same machine (cpu, torch 2.5.1).

| metric | A: symbolic + FluidSynth (this engine) | B: MusicGen-small + Demucs |
|---|---|---|
| CLAP prompt match (mean cos, laion/clap-htsat-unfused) | 0.508 | 0.454 |
| wall seconds per 30 s clip | 2.4 | 170.4 (generate 155.8 + separate 14.6) |
| seconds per 60 s of music | 4.9 | 340.8 |
| length error vs requested | 0.0000 s (max) | 0.0600 s (max); no bar-aligned ending control |
| stems | 4 rendered parts (drums, bass, harmony, melody) | 4 separated estimates (bass, drums, other, vocals) |
| stem sum vs mix | -116.5 dB | -34.0 dB |
| max abs waveform xcorr between stems | 0.020 | 0.227 |
| shared-content index (NNLS explained, dB) | -9.1 | -5.2 |
| loudness before mastering | mastered to -16.0 LUFS | -18.7 LUFS raw (needs mastering) |
| licence for commercial use | owned code + MIT SoundFont + permissive libs | **MusicGen weights CC-BY-NC-4.0: non-commercial only**; Demucs MIT |
| API fees | 0 | 0 (self-hosted); GPU rental otherwise |

Per-case numbers: `eval/results/approach_metrics.json`.

Notes:
- **Small sample:** n = 5 prompts and one seed, so the CLAP difference (A 0.508 vs B 0.454) is too small and too few to call A "better sounding". It shows only that A is not worse on this independent metric.
- **Hardware:** B ran on CPU. A GPU would cut its 341 s per 60 s substantially, but would add rental cost, and the licence blocker remains either way.
- **B's stems:** they are estimates. The −34 dB sum difference and 0.23 cross-correlation show real leakage. B also has a "vocals" stem the brief does not want, and its length is quantised to codec frames (0.06 s short of 30 s, outside the ±0.05 s tolerance before any trim).

Recommendation stands: **A for production now.** Reconsider B, or a hybrid, only with a commercially licensed model and when stems are generated per part rather than separated.

## 7. Production numbers

Load tests used 8 concurrent 60 s jobs per setting ([eval/results/loadtest.jsonl](eval/results/loadtest.jsonl)):

| `WORKER_CONCURRENCY` | generation p50 (s) | latency p50 / p95 (s) | music-minutes per hour | peak RSS per job / worker tree (MB) |
|---|---|---|---|---|
| 1 | 5.0 | 22.2 / 39.7 | 685 | 661 / 941 |
| 2 | 7.2 | 17.0 / 28.7 | 997 | 662 / 1733 |
| 4 | 13.1 | 19.7 / 27.4 | 1029 | 666 / 2822 |

- **Seconds per 60 s of music:** cold (first job after the worker starts) **5.76 s**, warm **5.81 s**. There is no cold-start penalty, because no model is loaded. Each job is a fresh process.
- **300 s job:** 23.3 s, with a peak RSS of 2.2 GB.
- **Over the 48-case batch:** 4.0–16.4 s per 60 s while other jobs ran concurrently; mean real-time factor 10×.
- **Throttling:** an earlier run of the same load test gave 1,603 music-min/h at concurrency 4 ([loadtest_before_memory_fix.jsonl](eval/results/loadtest_before_memory_fix.jsonl)). The fanless laptop throttles under sustained load, so treat these as indicative, and re-measure on the target server.
- **Cost per minute** = server $/h ÷ music-minutes per hour. Compute is the only cost; API fees are $0. At an assumed **$0.10/h** server price this is $0.10 / 997 ≈ **$0.0001 per music-minute** (concurrency 2). Substitute your server's real price; the throughput is the measured part.
- **Concurrent jobs per server:** CPU-bound. On this host, throughput stopped improving beyond 2 workers. Memory per job is about 0.66 GB at 60 s and 2.2 GB at 300 s, so a 4 vCPU / 8 GB server should run `WORKER_CONCURRENCY=2`. This is a recommendation, not measured on that server.

## 7a. Failures found and fixed (kept as evidence)

| Found by | Problem | Fix | Evidence |
|---|---|---|---|
| Batch run 1 (46/48) | Pizzicato, piano and mallet harmony "sustained" chords decayed, leaving gaps (`p07_playful`, min RMS −90 dBFS) | Decaying GM programs re-strike every 1–2 beats | [testpack/run1_failures/](testpack/run1_failures/) |
| Batch run 1 | The RMS-flux onset detector missed the final hit after a loud peak section (`d010`) | Spectral-flux onset function; threshold 2× median (all hits measured 2.6–64×) | same |
| Load test | A 300 s job peaked at **5.1 GB** RSS | float32 audio path, in-place mastering, chunked spectral flux, stems streamed in the QA gate: **2.2 GB**; 60 s jobs 1.66 → 0.66 GB | loadtest files |
| Mastering design | The plan's p95 click threshold flagged intentional crash cymbals at section downbeats | Reference raised to p99 of 40 ms-window maxima; a synthetic 0.3 FS step is still caught (`test_click_detector_finds_a_real_discontinuity`) | `qa.click_report` |
| Evidence run ev1 | A 120 s cinematic track (seed 200) failed `MIX_QA_FAILED`: a drum fill landing on the peak crash scored 2.16 against the 2.0 click ratio, with the tonal stems smooth (a false positive) | Ratio raised to 3.0 (owner's choice); regression test `test_regression_drum_fill_on_crash_is_not_a_click` | `evidence/runs/ev1/duration_120s/` |
| Evidence run ev1 | A SIGKILLed worker supervisor left its worker processes running outside Docker; they kept claiming jobs | Worker and job processes exit when their parent dies; `test_children_exit_when_supervisor_is_killed` | `src/musicengine/worker/loop.py` |
| CLAP evaluation | `larger_clap_music` text embeddings collapsed | Switched to `clap-htsat-unfused` after a sanity check | eval/README.md |

## 8. Not done or not verified (honest list)

- **Docker:** `docker compose up` / `make test` were not executed (no Docker on the build machine). The same code was verified natively.
- **Demo:** no public demo deployment, uptime monitor or demo video yet. `deploy/` holds an untested Caddy override.
- **Human tasks:** the blind listening test and the human listening notes are not done.
- **Real server:** production numbers come from a laptop, not the target VPS.

## 9. Claim → evidence index

| Claim | File |
|---|---|
| 48/48 batch cases, all metrics | `testpack/run3/summary.csv`, `testpack/run3/metrics.csv`, `testpack/run3/cases/*/qa.json` |
| Run-1 failures | `testpack/run1_failures/` |
| Bleed / overlap | `eval/results/bleed.md` |
| CLAP | `eval/results/clap.md` |
| Load / cost / RAM | `eval/results/loadtest*.jsonl` |
| Approach B | `eval/results/approach_comparison.md`, `eval/results/approach_metrics.json` |
| Licences | `SOURCES.md`, `licenses.yaml`, `eval/README.md` |
| Test suite | `tests/` (352 tests) |
