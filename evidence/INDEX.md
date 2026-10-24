# Evidence index (claim -> files)

Run `ev3`, commit `28bda2d802da`. Regenerate: `make evidence`.

| claim (form cell) | verdict | value | evidence |
|---|---|---|---|
| 1_Your_Details!B10 (D_TOKEN) | HUMAN |  |  |
| 1_Your_Details!B11 (D_COLD_START) | HUMAN | none (always-on); first job after a worker restart: cold 5.4 s / warm 5.4 s per 60 s of music (median of 5 war | evidence/metrics/speed.csv |
| 1_Your_Details!B12 (D_REPO) | HUMAN |  |  |
| 1_Your_Details!B14 (D_REPORT) | HUMAN | REPORT.md | REPORT.md |
| 1_Your_Details!B15 (D_COMPUTE) | PASS | Laptop: Mac17,3 (Apple M5, 10 cores, 16.0 GB RAM, macOS-26.5.2-arm64-arm-64bit); GPU: none | evidence/metrics/hardware.json |
| 1_Your_Details!B16 (D_PAID) | HUMAN | None, $0: no paid API, cloud service or GPU was used to produce or measure any output | evidence/metrics/costs.json |
| 1_Your_Details!B17 (D_AI_TOOLS) | HUMAN | Claude Code (Anthropic, Claude Opus 5.5) wrote code, tests and docs from my plan; details in AI_USE.md | AI_USE.md |
| 1_Your_Details!B9 (D_DEMO_URL) | HUMAN |  | evidence/baseline.json |
| 2_Must_haves!C10 (MH5) | PASS | 58 mixes: 48 kHz 24-bit WAV; ffmpeg LUFS -16.5..-16.0 (target -16); TP worst -1.1 dBTP; 0 clicks/gaps/clipped | evidence/must_haves/mh5_audio/loudness_table.csv<br>evidence/must_haves/mh5_audio/truepeak_table.csv<br>evidence/must_haves/mh5_audio/click_gap_report.csv |
| 2_Must_haves!C11 (MH6) | FAIL | integration 9/10 PASS; demo not deployed | evidence/baseline.json<br>evidence/integration |
| 2_Must_haves!C6 (MH1) | PASS | max /error/ 0 samples over 294 files; endings 58/58 | evidence/must_haves/mh1_length/report.md<br>tests/unit/test_timegrid.py<br>evidence/must_haves/mh1_length/lengths.csv |
| 2_Must_haves!C7 (MH2) | PASS | 4 stems per run; sum-vs-mix worst -114.9 dB over 52 runs | evidence/must_haves/mh2_stems/sum_diff.csv<br>evidence/must_haves/mh2_stems/stem_inventory.csv<br>evidence/must_haves/mh2_stems/source_check.md |
| 2_Must_haves!C8 (MH3) | PASS | 0 vocal GM programs in 232 stems; 2 vocal prompts stayed instrumental | evidence/must_haves/mh3_instrumental/programs_used.csv<br>evidence/must_haves/mh3_instrumental/vocal_prompt_cases.csv<br>tests/unit/test_interpreter.py |
| 2_Must_haves!C9 (MH4) | PASS | 17 components with licence URL + quoted clause; no AGPL/NC in the generation path | SOURCES.md<br>licenses.yaml<br>evidence/must_haves/mh4_licences/agpl_scan.txt |
| 3_Levels!C10 (L_DUCKING) | PASS | 3 narrations with speech pass (mean depth 12.0 dB, 12.0 dB, 12.0 dB); 2 no-speech case(s) flat | evidence/levels/adv_ducking/depth.csv<br>evidence/levels/adv_ducking/curve_narration_gaps.png |
| 3_Levels!C11 (L_REGEN) | PASS | 2 regenerations (drums, melody): other stems SHA-256 identical, new mixes pass QA | evidence/levels/adv_regen/hash_compare.txt |
| 3_Levels!C12 (L_LOOP) | PASS | 3/3 loops: no click at the joint, grid phase error <= 0.0000 ms | evidence/levels/adv_loop/seam.csv<br>evidence/levels/adv_loop/seam_plot.png |
| 3_Levels!C13 (L_MEASURED_QUALITY) | PENDING_HUMAN | CLAP (laion/clap-htsat-unfused) matched 0.472 vs mismatched 0.338 over 12 prompts; bleed/xcorr per stem in ble | evidence/eval/clap.csv<br>evidence/eval/bleed.csv<br>eval/listening_test.md |
| 3_Levels!C14 (L_TWO_APPROACHES) | PASS | A vs B on 5 prompts: CLAP 0.508 vs 0.454; 4.9 vs 340.8 s per 60 s; $0.000135 vs $0.009467/min; recommend A | evidence/eval/approach_comparison.md<br>evidence/eval/approach_comparison.csv<br>REPORT.md |
| 3_Levels!C15 (L_PRODUCTION) | PASS | 60 s of music in 5.4 s warm / 5.4 s cold; $0.000062/min compute; best 1876 music-min/h at WORKER_CONCURRENCY=4 | evidence/metrics/speed.csv<br>evidence/metrics/load.csv<br>evidence/metrics/costs.json |
| 3_Levels!C5 (L_ALL_MUST_HAVES) | FAIL | must-haves: {'MH1': 'PASS', 'MH2': 'PASS', 'MH3': 'PASS', 'MH4': 'PASS', 'MH5': 'PASS', 'MH6': 'FAIL'} | evidence/verdicts.json |
| 3_Levels!C6 (L_CORE_PROMPTS) | PENDING_HUMAN | 12 prompts -> 12 distinct presets, all QA PASS | evidence/levels/core_prompts/preset_distinct.csv<br>evidence/levels/core_prompts |
| 3_Levels!C7 (L_DURATIONS) | PASS | 5, 6, 10, 30, 60, 120, 180, 300 s all QA PASS | evidence/levels/core_durations/matrix.csv |
| 3_Levels!C8 (L_SECTIONS) | PASS | 72/72 section changes aligned in 48/48 runs | evidence/levels/adv_sections/alignment.csv<br>evidence/levels/adv_sections/plots |
| 3_Levels!C9 (L_ONE_PIECE) | PASS | one tempo + key per manifest; drum onsets vs manifest downbeats: worst median 18.8 ms over 47 runs (limit 20 m | evidence/levels/adv_one_piece/grid_check.csv |
| 4_Integration!C10 (I6) | PASS | 8 literal hits, 0 unexplained; every setting via env (config.py) | evidence/integration/config_scan.txt<br>src/musicengine/config.py<br>.env.example |
| 4_Integration!C11 (I7) | PASS | narration by upload:// and by http(s) URL both work; outputs in S3 (MinIO) as presigned links | evidence/integration/files_io.txt |
| 4_Integration!C12 (I8) | PASS | 90 JSON log lines: timestamp, level, event, job_id, correlation_id == request header; /health 200, /ready 200 | evidence/integration/logs_sample.jsonl<br>evidence/integration/health.txt |
| 4_Integration!C13 (I9) | PASS | 58 manifests validate; providers+versions, settings, seed, timings, cost, warnings, licences present | evidence/integration/manifest_schema_check.txt<br>src/musicengine/manifest.py |
| 4_Integration!C14 (I10) | PASS | python -m musicengine.cli batch --api URL --input <folder> --out <folder>: all results in one folder | evidence/integration/batch_runner.txt<br>src/musicengine/cli.py |
| 4_Integration!C5 (I1) | PARTIAL | compose not executed (no Docker here); full suite passes natively | evidence/integration/compose_up.txt<br>evidence/integration/make_test_output.txt<br>.env.example |
| 4_Integration!C6 (I2) | PASS | OpenAPI 3.1.0; committed file == running service: True | openapi.yaml<br>evidence/integration/openapi_diff.txt |
| 4_Integration!C7 (I3) | PASS | 202 + job_id; statuses ['failed', 'queued', 'running', 'succeeded']; progress 0-100; signed callback verified | evidence/integration/jobs_flow.txt<br>evidence/runs/ev3/io_callback |
| 4_Integration!C8 (I4) | PASS | same key+body (sequential and parallel) -> same job_id, worked once; different body -> 409 | evidence/integration/idempotency.txt |
| 4_Integration!C9 (I5) | PASS | 16 error + 19 warning codes, all in README; JSON shape on every probe | evidence/integration/errors_catalog.txt<br>README.md |
| 5_Metrics!C10 (METRIC_PROMPT_MATCH) | PARTIAL | CLAP 0.472 ± 0.150 (mismatched control 0.338, matched higher in 9/12); listening test: not run yet | evidence/eval/clap.csv<br>evidence/eval/control_clap.csv |
| 5_Metrics!C5 (METRIC_SPEED) | PASS | cold 5.4 s / warm 5.4 s per 60 s of music (median of 5 warm runs) | evidence/metrics/speed.csv<br>evidence/metrics/hardware.json |
| 5_Metrics!C6 (METRIC_COST) | PASS | $0.000062 per minute of music (compute only; API fees $0) | evidence/metrics/costs.json |
| 5_Metrics!C7 (METRIC_LENGTH) | PASS | max /Δ/ = 0 samples (0.000000 s) across 294 files (mix, ducked mix and stems) | evidence/must_haves/mh1_length/lengths.csv |
| 5_Metrics!C8 (METRIC_LOUDNESS) | PASS | LUFS -16.5..-16.0 (target -16, ffmpeg ebur128) and max true peak -1.1 dBTP over 58 mixes | evidence/metrics/loudness_table.csv |
| 5_Metrics!C9 (METRIC_STEMS) | PASS | sum-vs-mix worst -114.9 dB; max /xcorr/ between stems 0.165; shared-content index (mean dB) drums -13.2, bass  | evidence/metrics/stem_quality.csv |
| 6_Hard_cases!C10 (HC6) | PASS | Yes | evidence/hard_cases/hc6 |
| 6_Hard_cases!C11 (HC7) | PASS | Yes | evidence/hard_cases/hc7 |
| 6_Hard_cases!C12 (HC8) | PASS | Yes | evidence/hard_cases/hc8 |
| 6_Hard_cases!C5 (HC1) | PASS | Yes | evidence/hard_cases/hc1 |
| 6_Hard_cases!C6 (HC2) | PASS | Yes | evidence/hard_cases/hc2 |
| 6_Hard_cases!C7 (HC3) | PASS | Yes | evidence/hard_cases/hc3 |
| 6_Hard_cases!C8 (HC4) | PASS | Yes | evidence/hard_cases/hc4 |
| 6_Hard_cases!C9 (HC5) | PASS | Yes | evidence/hard_cases/hc5<br>evidence/levels/adv_ducking/depth.csv |
| 7_Declaration!support (SECRETS) | FAIL | secret scan | evidence/security/secret_scan.txt |
| meta!consistency (CONSISTENCY) | PASS | 19/19 quoted numbers match their sources; 0 missing paths | evidence/consistency.txt |

## REPORT.md claims

| REPORT.md section | evidence |
|---|---|
| 3 Must-haves measured | evidence/must_haves/*, evidence/metrics/loudness_table.csv |
| 4 Prompt match | evidence/eval/clap.csv, eval/results/clap.md |
| 5 Stem cleanliness | evidence/metrics/stem_quality.csv, eval/results/bleed.md |
| 6 Approach B | evidence/eval/approach_comparison.md |
| 7 Production numbers | evidence/metrics/speed.csv, load.csv, costs.json |
| 7a Failures found | evidence/runs/ev1/duration_120s/, testpack/run1_failures/ |
