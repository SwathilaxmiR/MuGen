# Test pack

| Folder | Contents |
|---|---|
| `run3/` | Final batch run (48/48 passed): `summary.csv`, `metrics.csv`, and per case `request.json`, `status.json`, `checks.json`, `qa.json`, `music_manifest.json` |
| `run1_failures/` | First batch run (46/48): the two `MIX_QA_FAILED` jobs (playful gaps, missed final-hit onset), kept as evidence; fixed in commit "T11" |

Presigned URLs were stripped of their query strings (signatures and credentials). The audio itself (mix, stems, mp3, ducked mix for every case) is not committed because of its size. Regenerate the full audio pack with:

```bash
python -m musicengine.cli batch --api http://localhost:8000 --input tests/inputs --out out/batch3 --run-id v3
```

That writes `out/batch3/<case>/{mix.wav, mix.mp3, stems/*.wav, mix_ducked.wav, music_manifest.json, status.json, qa.json}`.
