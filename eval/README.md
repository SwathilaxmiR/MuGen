# Evaluation (offline, not part of the service image)

| Script | What it measures | Output |
|---|---|---|
| `bleed.py` | Stem cleanliness: shared-content index (NNLS), waveform cross-correlation, spectral overlap vs a band-split control, sum difference | `results/bleed.md` |
| `loadtest.py` | K concurrent jobs: p50/p95 latency, jobs/hour, music-minutes/hour, peak RSS, $/min from a given $/h | `results/loadtest.jsonl`, `results/loadtest_before_memory_fix.jsonl` |
| `clap_score.py` | Prompt match with an independent model (CLAP); matched-vs-mismatched control; retrieval rank; ours vs baseline | `results/clap.md`, `results/clap_a30.md` |
| `make_listening_pack.py` + `listening_test.md` | Blind A/B pack, ours vs baseline (**human test not run yet**) | `out/listening_pack/` |
| `approach_b.py` + `approach_b_metrics.py` | Approach B (MusicGen-small + Demucs) vs this engine on the same prompts | `results/approach_metrics.json`, `results/approach_comparison.md` |

Environment: `uv venv eval/.venv --python 3.12 && uv pip install --python eval/.venv -r eval/requirements.txt torchaudio==2.5.1 demucs`. Run the model scripts with `HF_HOME=eval/.cache`. `bleed.py`, `loadtest.py`, `make_listening_pack.py` and `approach_b_metrics.py` use the main `.venv`.

## Models and licences (evaluation only)

| Component | Licence (as published) | Used for |
|---|---|---|
| `laion/clap-htsat-unfused` (via transformers) | Apache-2.0 (Hugging Face model card) | Prompt-match scoring |
| `laion/larger_clap_music` | Apache-2.0 | Tried first and **rejected**: under transformers 4.46.3 and 5.20.2 its text tower gave cosine 1.00 between "jazz music" and "birds chirping", so it cannot score prompts |
| `facebook/musicgen-small` | **CC-BY-NC-4.0 (non-commercial)** | Approach B generator. This licence is the reason it cannot ship |
| Demucs 4 / `htdemucs` | MIT | Approach B source separation |
| PyTorch 2.5.1, transformers 4.46.3 | BSD-3-Clause, Apache-2.0 | Runtime for the above (torch 2.14 + transformers 5.20 also showed the broken-text-embedding symptom, so versions are pinned) |

The CLAP sanity check that decided the model choice:
- `clap-htsat-unfused` scores our jazz output 0.545 for the "smooth jazz lounge with saxophone" prompt against 0.069 for "birds chirping", and our rock output 0.642 for the rock prompt.
- `larger_clap_music` returned about 0.00 for every text.
