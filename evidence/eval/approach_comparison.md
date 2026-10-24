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


**Cost per minute of music** (same machine, CPU, at an assumed $0.1/h): A $0.000135, B $0.009467. API fees $0 for both (self-hosted).

**Recommendation:** run A in production: exact length and stems by construction, ~70x faster, licence-clean; B's open weights are non-commercial. Source: REPORT.md section 6.
