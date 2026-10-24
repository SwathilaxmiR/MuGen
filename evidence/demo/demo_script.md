# Demo video script (<= 8 min, one take, unedited)

Record the screen and terminal. Replace each `VIDEO@` placeholder in `evidence/form_inputs.yaml` with the real
`mm:ss` after recording; the form filler copies them into the evidence cells.

| Target | Placeholder | Do | Expected |
|---|---|---|---|
| 00:00 | VIDEO@intro | `git log --oneline \| head -3`, `curl -s $DEMO/health` | `git_sha` equals the tag `submission-v1` |
| 00:30 | VIDEO@clean_run | Web UI: example "Calm cinematic piano...", 45 s, Generate | progress steps, then the mix, 4 stems, timeline, facts (-16.0 LUFS, -1.6 dBTP) |
| 02:00 | VIDEO@stems | Play two stems solo; download the manifest; show `stems[]`, `beats`, `loudness`, `ai_generated` | stems are separate parts; manifest fields present |
| 02:45 | VIDEO@regen | Click Regenerate on Drums | new version; the other three stems are byte-identical (`evidence/levels/adv_regen/hash_compare.txt`) |
| 03:30 | VIDEO@failure | `curl -X POST $DEMO/api/v1/music/jobs -d '{"prompt":"x","duration_s":400}'` and a vocals prompt in the UI | 422 VALIDATION_ERROR JSON; the vocals job succeeds with a VOCALS_NOT_SUPPORTED note |
| 04:15 | VIDEO@fallback | Locally: `FAULT_INJECT=render_primary_fail` worker, one job | job succeeds with PROVIDER_FALLBACK_USED; manifest renderer = numpy |
| 05:00 | VIDEO@tests | `make test` (or `pytest tests`) | all tests pass, no API keys |
| 06:30 | VIDEO@design | Open `src/musicengine/mixdown.py::master` and `planner/timegrid.py` | explain: one limiter curve from the sum applied to every stem, so mix = sum of stems; length planned in whole bars |
| 07:45 | VIDEO@end | Close | |
