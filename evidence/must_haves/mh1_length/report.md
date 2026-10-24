# MH1 exact length and ending

294 WAV files (mix, ducked mix, every stem) over 58 runs.

- Max |length error|: **0 samples** (limit 0.05 s = 2400 samples at 48 kHz).
- Endings: 58/58 pass (last 50 ms < -60 dBFS; non-loop: onset at the hit (spectral flux >= 2x median) and the hit on a manifest bar line, or on a beat with ENDING_ON_BEAT_NOT_BAR).
- Unit tests `tests/unit/test_timegrid.py`: pass.
- Listening (10 clips in `last3s/`): **HUMAN**, record in `evidence/listening/log.csv`.
