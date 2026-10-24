# FORM_REPORT

Generated 2026-10-24T07:28:44+00:00 from `evidence/verdicts.json` (evidence run `ev3`, commit `28bda2d802da`) by `scripts/fill_form.py`. Output: `Assessment1_YourName.xlsx` (git-ignored).

## Self-check (the form's GREEN cells)

| | |
|---|---|
| must_haves_yes | 5 of 6 |
| level | None |
| level_marks | 0 |
| integration_marks | 19 |
| self_assessed_total_60 | 19 |
| formula_check | =IF(AND(AND(COUNTIF(C5:C7,"Yes")=3,COUNT... |
| note | computed in Python (LibreOffice not installed); Excel recalculates on open (fullCalcOnLoad) |

## Every filled cell

| cell | value | verdict key | evidence |
|---|---|---|---|
| 2_Must_haves!C6 | Yes | MH1 | evidence/must_haves/mh1_length/report.md; tests/unit/test_timegrid.py; evidence/must_haves/mh1_length/lengths.csv |
| 2_Must_haves!D6 | evidence/must_haves/mh1_length/report.md ; tests/unit/test_timegrid.py ; evidence/must_haves/mh1_length/lengths.csv | MH1 | evidence/must_haves/mh1_length/report.md; tests/unit/test_timegrid.py; evidence/must_haves/mh1_length/lengths.csv |
| 2_Must_haves!E6 | max /error/ 0 samples over 294 files; endings 58/58. Every mix and stem is exactly round(D*sr) samples; final hit on a bar line, decays to < | MH1 | evidence/must_haves/mh1_length/report.md; tests/unit/test_timegrid.py; evidence/must_haves/mh1_length/lengths.csv |
| 5_Metrics!C7 | max /Δ/ = 0 samples (0.000000 s) across 294 files (mix, ducked mix and stems) | METRIC_LENGTH | evidence/must_haves/mh1_length/lengths.csv |
| 5_Metrics!D7 | 58 runs, durations 5-300 s | METRIC_LENGTH | evidence/must_haves/mh1_length/lengths.csv |
| 5_Metrics!E7 | evidence/must_haves/mh1_length/lengths.csv | METRIC_LENGTH | evidence/must_haves/mh1_length/lengths.csv |
| 2_Must_haves!C7 | Yes | MH2 | evidence/must_haves/mh2_stems/sum_diff.csv; evidence/must_haves/mh2_stems/stem_inventory.csv; evidence/must_haves/mh2_stems/source_check.md |
| 2_Must_haves!D7 | evidence/must_haves/mh2_stems/sum_diff.csv ; evidence/must_haves/mh2_stems/stem_inventory.csv ; evidence/must_haves/mh2_stems/source_check.m | MH2 | evidence/must_haves/mh2_stems/sum_diff.csv; evidence/must_haves/mh2_stems/stem_inventory.csv; evidence/must_haves/mh2_stems/source_check.md |
| 2_Must_haves!E7 | 4 stems per run; sum-vs-mix worst -114.9 dB over 52 runs. mix = Σ gain·stem with manifest gains 1.0; worst difference -114.9 dB (24-bit roun | MH2 | evidence/must_haves/mh2_stems/sum_diff.csv; evidence/must_haves/mh2_stems/stem_inventory.csv; evidence/must_haves/mh2_stems/source_check.md |
| 5_Metrics!C9 | sum-vs-mix worst -114.9 dB; max /xcorr/ between stems 0.165; shared-content index (mean dB) drums -13.2, bass -10.8, harmony -10.2, melody - | METRIC_STEMS | evidence/metrics/stem_quality.csv |
| 5_Metrics!D9 | 52 runs. The shared-content index measures shared key/rhythm, not leakage (see eval/bleed.md). | METRIC_STEMS | evidence/metrics/stem_quality.csv |
| 5_Metrics!E9 | evidence/metrics/stem_quality.csv | METRIC_STEMS | evidence/metrics/stem_quality.csv |
| 2_Must_haves!C8 | Yes | MH3 | evidence/must_haves/mh3_instrumental/programs_used.csv; evidence/must_haves/mh3_instrumental/vocal_prompt_cases.csv; tests/unit/test_interpreter.py |
| 2_Must_haves!D8 | evidence/must_haves/mh3_instrumental/programs_used.csv ; evidence/must_haves/mh3_instrumental/vocal_prompt_cases.csv ; tests/unit/test_inter | MH3 | evidence/must_haves/mh3_instrumental/programs_used.csv; evidence/must_haves/mh3_instrumental/vocal_prompt_cases.csv; tests/unit/test_interpreter.py |
| 2_Must_haves!E8 | 0 vocal GM programs in 232 stems; 2 vocal prompts stayed instrumental. GM voice/choir programs 52-54, 85, 91 cannot be loaded (preset valida | MH3 | evidence/must_haves/mh3_instrumental/programs_used.csv; evidence/must_haves/mh3_instrumental/vocal_prompt_cases.csv; tests/unit/test_interpreter.py |
| 2_Must_haves!C9 | Yes | MH4 | SOURCES.md; licenses.yaml; evidence/must_haves/mh4_licences/agpl_scan.txt |
| 2_Must_haves!D9 | SOURCES.md ; licenses.yaml ; evidence/must_haves/mh4_licences/agpl_scan.txt | MH4 | SOURCES.md; licenses.yaml; evidence/must_haves/mh4_licences/agpl_scan.txt |
| 2_Must_haves!E9 | 17 components with licence URL + quoted clause; no AGPL/NC in the generation path. MinIO (AGPL-3.0) is the compose/demo object store only; s | MH4 | SOURCES.md; licenses.yaml; evidence/must_haves/mh4_licences/agpl_scan.txt |
| 2_Must_haves!C10 | Yes | MH5 | evidence/must_haves/mh5_audio/loudness_table.csv; evidence/must_haves/mh5_audio/truepeak_table.csv; evidence/must_haves/mh5_audio/click_gap_report.csv |
| 2_Must_haves!D10 | evidence/must_haves/mh5_audio/loudness_table.csv ; evidence/must_haves/mh5_audio/truepeak_table.csv ; evidence/must_haves/mh5_audio/click_ga | MH5 | evidence/must_haves/mh5_audio/loudness_table.csv; evidence/must_haves/mh5_audio/truepeak_table.csv; evidence/must_haves/mh5_audio/click_gap_report.csv |
| 2_Must_haves!E10 | 58 mixes: 48 kHz 24-bit WAV; ffmpeg LUFS -16.5..-16.0 (target -16); TP worst -1.1 dBTP; 0 clicks/gaps/clipped. Independent ffmpeg ebur128 an | MH5 | evidence/must_haves/mh5_audio/loudness_table.csv; evidence/must_haves/mh5_audio/truepeak_table.csv; evidence/must_haves/mh5_audio/click_gap_report.csv |
| 5_Metrics!C8 | LUFS -16.5..-16.0 (target -16, ffmpeg ebur128) and max true peak -1.1 dBTP over 58 mixes | METRIC_LOUDNESS | evidence/metrics/loudness_table.csv |
| 5_Metrics!D8 | meters agree within 0.08 LU | METRIC_LOUDNESS | evidence/metrics/loudness_table.csv |
| 5_Metrics!E8 | evidence/metrics/loudness_table.csv | METRIC_LOUDNESS | evidence/metrics/loudness_table.csv |
| 3_Levels!D6 | evidence/levels/core_prompts/preset_distinct.csv ; evidence/levels/core_prompts | L_CORE_PROMPTS | evidence/levels/core_prompts/preset_distinct.csv; evidence/levels/core_prompts |
| 3_Levels!C7 | Yes | L_DURATIONS | evidence/levels/core_durations/matrix.csv |
| 3_Levels!D7 | evidence/levels/core_durations/matrix.csv | L_DURATIONS | evidence/levels/core_durations/matrix.csv |
| 3_Levels!E7 | 5, 6, 10, 30, 60, 120, 180, 300 s all QA PASS. plus 5, 6 and 300 s hard cases. Reproduce: make evidence | L_DURATIONS | evidence/levels/core_durations/matrix.csv |
| 3_Levels!C8 | Yes | L_SECTIONS | evidence/levels/adv_sections/alignment.csv; evidence/levels/adv_sections/plots |
| 3_Levels!D8 | evidence/levels/adv_sections/alignment.csv ; evidence/levels/adv_sections/plots | L_SECTIONS | evidence/levels/adv_sections/alignment.csv; evidence/levels/adv_sections/plots |
| 3_Levels!E8 | 72/72 section changes aligned in 48/48 runs. every applied start is a manifest beat; 8 user-requested starts all within 0.5 s (max /snap/ 0. | L_SECTIONS | evidence/levels/adv_sections/alignment.csv; evidence/levels/adv_sections/plots |
| 3_Levels!C9 | Yes | L_ONE_PIECE | evidence/levels/adv_one_piece/grid_check.csv |
| 3_Levels!D9 | evidence/levels/adv_one_piece/grid_check.csv | L_ONE_PIECE | evidence/levels/adv_one_piece/grid_check.csv |
| 3_Levels!E9 | one tempo + key per manifest; drum onsets vs manifest downbeats: worst median 18.8 ms over 47 runs (limit 20 ms). All four stems are rendere | L_ONE_PIECE | evidence/levels/adv_one_piece/grid_check.csv |
| 3_Levels!C10 | Yes | L_DUCKING | evidence/levels/adv_ducking/depth.csv; evidence/levels/adv_ducking/curve_narration_gaps.png |
| 3_Levels!D10 | evidence/levels/adv_ducking/depth.csv ; evidence/levels/adv_ducking/curve_narration_gaps.png | L_DUCKING | evidence/levels/adv_ducking/depth.csv; evidence/levels/adv_ducking/curve_narration_gaps.png |
| 3_Levels!E10 | 3 narrations with speech pass (mean depth 12.0 dB, 12.0 dB, 12.0 dB); 2 no-speech case(s) flat. Rule needs >= 3 narrations with speech. Repr | L_DUCKING | evidence/levels/adv_ducking/depth.csv; evidence/levels/adv_ducking/curve_narration_gaps.png |
| 3_Levels!C11 | Yes | L_REGEN | evidence/levels/adv_regen/hash_compare.txt |
| 3_Levels!D11 | evidence/levels/adv_regen/hash_compare.txt | L_REGEN | evidence/levels/adv_regen/hash_compare.txt |
| 3_Levels!E11 | 2 regenerations (drums, melody): other stems SHA-256 identical, new mixes pass QA. Reproduce: make evidence | L_REGEN | evidence/levels/adv_regen/hash_compare.txt |
| 3_Levels!C12 | Yes | L_LOOP | evidence/levels/adv_loop/seam.csv; evidence/levels/adv_loop/seam_plot.png |
| 3_Levels!D12 | evidence/levels/adv_loop/seam.csv ; evidence/levels/adv_loop/seam_plot.png | L_LOOP | evidence/levels/adv_loop/seam.csv; evidence/levels/adv_loop/seam_plot.png |
| 3_Levels!E12 | 3/3 loops: no click at the joint, grid phase error <= 0.0000 ms. Loop = N whole bars exactly; rendered twice, second pass kept, so tails wra | L_LOOP | evidence/levels/adv_loop/seam.csv; evidence/levels/adv_loop/seam_plot.png |
| 6_Hard_cases!C5 | Yes | HC1 | evidence/hard_cases/hc1 |
| 6_Hard_cases!D5 | 5-6 s: one section, 1-2 bars with the final hit on a bar line (hit 4.033613 s in a 5 s track), exact length. 300 s: same path, default intro | HC1 | evidence/hard_cases/hc1 |
| 6_Hard_cases!E5 | evidence/hard_cases/hc1 | HC1 | evidence/hard_cases/hc1 |
| 6_Hard_cases!C6 | Yes | HC2 | evidence/hard_cases/hc2 |
| 6_Hard_cases!D6 | Vague ('music'): neutral corporate preset at moderate energy, VAGUE_PROMPT_DEFAULTS. Contradictory ('calm but aggressive'): mid energy, mino | HC2 | evidence/hard_cases/hc2 |
| 6_Hard_cases!E6 | evidence/hard_cases/hc2 | HC2 | evidence/hard_cases/hc2 |
| 6_Hard_cases!C7 | Yes | HC3 | evidence/hard_cases/hc3 |
| 6_Hard_cases!D7 | Song/artist references ('like Interstellar by Hans Zimmer', quoted titles, 'cover of') are removed before planning and only generic mood wor | HC3 | evidence/hard_cases/hc3 |
| 6_Hard_cases!E7 | evidence/hard_cases/hc3 | HC3 | evidence/hard_cases/hc3 |
| 6_Hard_cases!C8 | Yes | HC4 | evidence/hard_cases/hc4 |
| 6_Hard_cases!D8 | After snapping to the beat, sections < 1.5 s apart are merged (earlier start, higher intensity, SECTIONS_MERGED_MIN_GAP); a section starting | HC4 | evidence/hard_cases/hc4 |
| 6_Hard_cases!E8 | evidence/hard_cases/hc4 | HC4 | evidence/hard_cases/hc4 |
| 6_Hard_cases!C9 | Yes | HC5 | evidence/hard_cases/hc5; evidence/levels/adv_ducking/depth.csv |
| 6_Hard_cases!D9 | Speech is detected with an energy VAD; in silences of 1 s or more the music returns to full level (500 ms release, curve in the manifest); g | HC5 | evidence/hard_cases/hc5; evidence/levels/adv_ducking/depth.csv |
| 6_Hard_cases!E9 | evidence/hard_cases/hc5 ; evidence/levels/adv_ducking/depth.csv | HC5 | evidence/hard_cases/hc5; evidence/levels/adv_ducking/depth.csv |
| 6_Hard_cases!C10 | Yes | HC6 | evidence/hard_cases/hc6 |
| 6_Hard_cases!D10 | Language is detected (script ranges + langdetect: {'hard_spanish': 'es', 'hard_hindi': 'hi', 'hard_tamil': 'ta', 'hard_unknown_language': 'r | HC6 | evidence/hard_cases/hc6 |
| 6_Hard_cases!E10 | evidence/hard_cases/hc6 | HC6 | evidence/hard_cases/hc6 |
| 6_Hard_cases!C11 | Yes | HC7 | evidence/hard_cases/hc7 |
| 6_Hard_cases!D11 | 4 jobs sent at the same moment are claimed independently (FOR UPDATE SKIP LOCKED) and all complete; the same request with the same Idempoten | HC7 | evidence/hard_cases/hc7 |
| 6_Hard_cases!E11 | evidence/hard_cases/hc7 | HC7 | evidence/hard_cases/hc7 |
| 6_Hard_cases!C12 | Yes | HC8 | evidence/hard_cases/hc8 |
| 6_Hard_cases!D12 | Renderer error or timeout: the stem is retried once, then rendered by the built-in numpy synth (PROVIDER_FALLBACK_USED, job succeeds); if ev | HC8 | evidence/hard_cases/hc8 |
| 6_Hard_cases!E12 | evidence/hard_cases/hc8 | HC8 | evidence/hard_cases/hc8 |
| 4_Integration!C6 | Yes | I2 | openapi.yaml; evidence/integration/openapi_diff.txt |
| 4_Integration!D6 | openapi.yaml ; evidence/integration/openapi_diff.txt | I2 | openapi.yaml; evidence/integration/openapi_diff.txt |
| 4_Integration!C7 | Yes | I3 | evidence/integration/jobs_flow.txt; evidence/runs/ev3/io_callback |
| 4_Integration!D7 | evidence/integration/jobs_flow.txt ; evidence/runs/ev3/io_callback | I3 | evidence/integration/jobs_flow.txt; evidence/runs/ev3/io_callback |
| 4_Integration!C8 | Yes | I4 | evidence/integration/idempotency.txt |
| 4_Integration!D8 | evidence/integration/idempotency.txt | I4 | evidence/integration/idempotency.txt |
| 4_Integration!C9 | Yes | I5 | evidence/integration/errors_catalog.txt; README.md |
| 4_Integration!D9 | evidence/integration/errors_catalog.txt ; README.md | I5 | evidence/integration/errors_catalog.txt; README.md |
| 4_Integration!C10 | Yes | I6 | evidence/integration/config_scan.txt; src/musicengine/config.py; .env.example |
| 4_Integration!D10 | evidence/integration/config_scan.txt ; src/musicengine/config.py ; .env.example | I6 | evidence/integration/config_scan.txt; src/musicengine/config.py; .env.example |
| 4_Integration!C11 | Yes | I7 | evidence/integration/files_io.txt |
| 4_Integration!D11 | evidence/integration/files_io.txt | I7 | evidence/integration/files_io.txt |
| 4_Integration!C12 | Yes | I8 | evidence/integration/logs_sample.jsonl; evidence/integration/health.txt |
| 4_Integration!D12 | evidence/integration/logs_sample.jsonl ; evidence/integration/health.txt | I8 | evidence/integration/logs_sample.jsonl; evidence/integration/health.txt |
| 4_Integration!C13 | Yes | I9 | evidence/integration/manifest_schema_check.txt; src/musicengine/manifest.py |
| 4_Integration!D13 | evidence/integration/manifest_schema_check.txt ; src/musicengine/manifest.py | I9 | evidence/integration/manifest_schema_check.txt; src/musicengine/manifest.py |
| 4_Integration!C14 | Yes | I10 | evidence/integration/batch_runner.txt; src/musicengine/cli.py |
| 4_Integration!D14 | evidence/integration/batch_runner.txt ; src/musicengine/cli.py | I10 | evidence/integration/batch_runner.txt; src/musicengine/cli.py |
| 4_Integration!C5 | Partial | I1 | evidence/integration/compose_up.txt; evidence/integration/make_test_output.txt; .env.example |
| 4_Integration!D5 | evidence/integration/compose_up.txt ; evidence/integration/make_test_output.txt ; .env.example | I1 | evidence/integration/compose_up.txt; evidence/integration/make_test_output.txt; .env.example |
| 5_Metrics!C5 | cold 5.4 s / warm 5.4 s per 60 s of music (median of 5 warm runs) | METRIC_SPEED | evidence/metrics/speed.csv; evidence/metrics/hardware.json |
| 5_Metrics!D5 | Mac17,3 (Apple M5, 10 cores, 16.0 GB RAM), CPU only, FluidSynth renderer; cold = first job after a worker restart; WORKER_CONCURRENCY=2; no  | METRIC_SPEED | evidence/metrics/speed.csv; evidence/metrics/hardware.json |
| 5_Metrics!E5 | evidence/metrics/speed.csv ; evidence/metrics/hardware.json | METRIC_SPEED | evidence/metrics/speed.csv; evidence/metrics/hardware.json |
| 5_Metrics!C6 | $0.000062 per minute of music (compute only; API fees $0) | METRIC_COST | evidence/metrics/costs.json |
| 5_Metrics!D6 | median 4.596 CPU-s per 60 s job x $1.34e-05/CPU-s (assumed $0.048 per vCPU-hour); by throughput: $5.3e-05/min at an assumed $0.1/h machine | METRIC_COST | evidence/metrics/costs.json |
| 5_Metrics!E6 | evidence/metrics/costs.json | METRIC_COST | evidence/metrics/costs.json |
| 3_Levels!C15 | Yes | L_PRODUCTION | evidence/metrics/speed.csv; evidence/metrics/load.csv; evidence/metrics/costs.json |
| 3_Levels!D15 | evidence/metrics/speed.csv ; evidence/metrics/load.csv ; evidence/metrics/costs.json | L_PRODUCTION | evidence/metrics/speed.csv; evidence/metrics/load.csv; evidence/metrics/costs.json |
| 3_Levels!E15 | 60 s of music in 5.4 s warm / 5.4 s cold; $0.000062/min compute; best 1876 music-min/h at WORKER_CONCURRENCY=4. load test 8 x 60 s at concur | L_PRODUCTION | evidence/metrics/speed.csv; evidence/metrics/load.csv; evidence/metrics/costs.json |
| 3_Levels!D13 | evidence/eval/clap.csv ; evidence/eval/bleed.csv ; eval/listening_test.md | L_MEASURED_QUALITY | evidence/eval/clap.csv; evidence/eval/bleed.csv; eval/listening_test.md |
| 3_Levels!C14 | Yes | L_TWO_APPROACHES | evidence/eval/approach_comparison.md; evidence/eval/approach_comparison.csv; REPORT.md |
| 3_Levels!D14 | evidence/eval/approach_comparison.md ; evidence/eval/approach_comparison.csv ; REPORT.md | L_TWO_APPROACHES | evidence/eval/approach_comparison.md; evidence/eval/approach_comparison.csv; REPORT.md |
| 3_Levels!E14 | A vs B on 5 prompts: CLAP 0.508 vs 0.454; 4.9 vs 340.8 s per 60 s; $0.000135 vs $0.009467/min; recommend A. Small sample (n=5, one seed); B  | L_TWO_APPROACHES | evidence/eval/approach_comparison.md; evidence/eval/approach_comparison.csv; REPORT.md |
| 5_Metrics!C10 | CLAP 0.472 ± 0.150 (mismatched control 0.338, matched higher in 9/12); listening test: not run yet | METRIC_PROMPT_MATCH | evidence/eval/clap.csv; evidence/eval/control_clap.csv |
| 5_Metrics!D10 | 12 core prompts at 45 s, laion/clap-htsat-unfused (Apache-2.0), CPU | METRIC_PROMPT_MATCH | evidence/eval/clap.csv; evidence/eval/control_clap.csv |
| 5_Metrics!E10 | evidence/eval/clap.csv ; evidence/eval/control_clap.csv | METRIC_PROMPT_MATCH | evidence/eval/clap.csv; evidence/eval/control_clap.csv |
| 2_Must_haves!C11 | No | MH6 | evidence/baseline.json; evidence/integration |
| 2_Must_haves!D11 | evidence/baseline.json ; evidence/integration | MH6 | evidence/baseline.json; evidence/integration |
| 2_Must_haves!E11 | integration 9/10 PASS; demo not deployed. No public demo is deployed yet, and docker compose has not been run (Integration 1 is Partial). | MH6 | evidence/baseline.json; evidence/integration |
| 3_Levels!C5 | No | L_ALL_MUST_HAVES | evidence/verdicts.json |
| 3_Levels!D5 | evidence/verdicts.json | L_ALL_MUST_HAVES | evidence/verdicts.json |
| 3_Levels!E5 | must-haves: {'MH1': 'PASS', 'MH2': 'PASS', 'MH3': 'PASS', 'MH4': 'PASS', 'MH5': 'PASS', 'MH6': 'FAIL'}. Needs every must-have PASS and the h | L_ALL_MUST_HAVES | evidence/verdicts.json |
| 1_Your_Details!B15 | Laptop: Mac17,3 (Apple M5, 10 cores, 16.0 GB RAM, macOS-26.5.2-arm64-arm-64bit); GPU: none | D_COMPUTE | evidence/metrics/hardware.json |
| 1_Your_Details!B16 | None, $0: no paid API, cloud service or GPU was used to produce or measure any output | D_PAID | evidence/metrics/costs.json |
| 1_Your_Details!B17 | Claude Code (Anthropic, Claude Opus 5.5) wrote code, tests and docs from my plan; details in AI_USE.md | D_AI_TOOLS | AI_USE.md |

## Needs a human

- 1_Your_Details!B4 (name)
- 1_Your_Details!B5 (email)
- 1_Your_Details!B6 (phone)
- 1_Your_Details!B7 (college_degree)
- 1_Your_Details!B8 (graduation_year)
- 1_Your_Details!B13 (video_url)
- 1_Your_Details!B18 (hours)
- 3_Levels!C6 (L_CORE_PROMPTS): PENDING_HUMAN - automated part passes; needs human 'matches' ratings on >= 10 prompts in listening/log.csv
- 3_Levels!C13 (L_MEASURED_QUALITY): PENDING_HUMAN - Blind A/B test with >= 5 listeners is a human task (eval/listening_test.md); until it is done this stays empty.
- 1_Your_Details!B9: Deploy, then set demo_url in evidence/form_inputs.yaml
- 1_Your_Details!B10: Token goes in the form only (form_inputs.yaml is git-ignored)
- 1_Your_Details!B11: Fill once the demo is deployed and always-on
- 1_Your_Details!B12: Set repo_url in form_inputs.yaml (private repo, reviewer invited)
- 1_Your_Details!B14: REPORT.md
- 1_Your_Details!B16: confirm 'None, $0: no paid API, cloud service or GPU was used to produce or mea'
- 1_Your_Details!B17: confirm 'Claude Code (Anthropic, Claude Opus 5.5) wrote code, tests and docs fr'
- Listening checks: fill `evidence/listening/log.csv` (clips in `evidence/listening/clips/`)
- Blind test with >= 5 people: put responses in `evidence/eval/blind_test/responses.csv` (columns listener, pair, preferred = ours/baseline/none, comment)
- Demo video from `evidence/demo/demo_script.md`; put the timestamps in `evidence/form_inputs.yaml`
- 7_Declaration (all 8 answers, signature, date): see `evidence/declaration_support.md`
- Then: commit evidence, `make evidence-form`, check this list is empty, tag `submission-v1`

## Cannot claim (FAIL / NOT_RUN / PARTIAL)

- 4_Integration!C5 (I1): Partial - compose not executed (no Docker here); full suite passes natively - Every setting is in .env.example. One test command, no API keys.
- 5_Metrics!C10 (METRIC_PROMPT_MATCH): PARTIAL CLAP 0.472 ± 0.150 (mismatched control 0.338, matched higher in 9/12); listening test: not run yet
- 2_Must_haves!C11 (MH6): No - integration 9/10 PASS; demo not deployed - No public demo is deployed yet, and docker compose has not been run (Integration 1 is Partial).
- 3_Levels!C5 (L_ALL_MUST_HAVES): No - must-haves: {'MH1': 'PASS', 'MH2': 'PASS', 'MH3': 'PASS', 'MH4': 'PASS', 'MH5': 'PASS', 'MH6': 'FAIL'} - Needs every must-have PASS and the human listening checks logged.

## Downgraded by the filler

- none

## Claims at risk

- 3_Levels row 6 'obviously matches the description' is judged by listening; CLAP agreement is modest (see 5_Metrics row 10).
- 2_Must_haves row 6: the demo must stay up for the whole review; nothing here proves future uptime.
- Docker: `make up` / `make test` have never run on this machine. Run them once on a Docker host before claiming Integration 1 as Yes.
- Measurements come from a fanless laptop; throughput varies under sustained load (eval/results/loadtest*.jsonl).
- The click detector threshold (ratio 3.0) was raised after evidence run ev1 flagged a drum fill as a click.
