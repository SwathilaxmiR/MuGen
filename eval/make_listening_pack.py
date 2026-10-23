"""Build the blind A/B listening pack: ours vs a simple baseline, randomised order, answer key kept apart.

    python eval/make_listening_pack.py --batch out/batch3 --out out/listening_pack

Baseline (as specified in the plan): one GM acoustic piano playing I-V-vi-IV block chords at a fixed
100 bpm in C major, looped and hard-trimmed to the duration, no sections, same loudness (-16 LUFS).
"""
import argparse
import csv
import json
import os
import random
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from musicengine import mixdown, qa  # noqa: E402
from musicengine.composer.base import Note, StemPart  # noqa: E402
from musicengine.config import Settings  # noqa: E402
from musicengine.renderer import get_renderer  # noqa: E402
from musicengine.renderer.base import RenderSpec  # noqa: E402

CASES = ["p01_cinematic", "p02_lofi", "p04_electronic", "p06_tense", "p07_playful", "p11_jazz"]
CHORDS = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]  # C G Am F


def baseline(duration_s: float, sr: int = 48000) -> np.ndarray:
    beat = 0.6  # 100 bpm
    notes, t = [], 0.0
    while t * beat < duration_s:
        for p in CHORDS[int(t // 4) % 4]:
            notes.append(Note(t, 1.9, p, 80))
        t += 2
    rs = RenderSpec(sr=sr, beat_s=beat, length=int(round(duration_s * sr)), loop=False, loop_beats=0)
    audio = get_renderer("fluidsynth", Settings()).render(StemPart("piano", 0, False, notes), rs)
    gain = 10 ** ((-16 - qa.integrated_lufs(audio, sr)) / 20)
    return audio * gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="out/batch3")
    ap.add_argument("--out", default="out/listening_pack")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    os.makedirs(a.out, exist_ok=True)
    key_rows, form = [], ["# Blind listening test\n",
                          "For each numbered pair, listen to **A** and **B** with the prompt in mind and answer: "
                          "*Which one fits the prompt better as background music?* (A / B / no preference), "
                          "plus an optional comment. Please do not look at the file metadata.\n"]
    for i, case in enumerate(CASES, 1):
        req = json.load(open(os.path.join(a.batch, case, "request.json")))
        ours, sr = mixdown.read_wav(os.path.join(a.batch, case, "mix.wav"))
        base = baseline(req["duration_s"], sr)
        ours_is_a = rnd.random() < 0.5
        pair = {"A": ours if ours_is_a else base, "B": base if ours_is_a else ours}
        for label, audio in pair.items():
            mixdown.write_wav(os.path.join(a.out, f"pair{i:02d}_{label}.wav"), audio, sr)
        key_rows.append({"pair": i, "case": case, "prompt": req["prompt"], "ours": "A" if ours_is_a else "B"})
        form.append(f"{i}. **Prompt:** \"{req['prompt']}\" ({req['duration_s']:g} s): `pair{i:02d}_A.wav` vs "
                    f"`pair{i:02d}_B.wav`")
    with open(os.path.join(a.out, "FORM.md"), "w") as fh:
        fh.write("\n".join(form) + "\n")
    os.makedirs(os.path.join(a.out, "..", "listening_key"), exist_ok=True)
    with open(os.path.join(a.out, "..", "listening_key", "answer_key.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["pair", "case", "prompt", "ours"])
        w.writeheader()
        w.writerows(key_rows)
    shutil.copy(__file__, os.path.join(a.out, "..", "listening_key", "generator.py"))
    print(f"pack -> {a.out} ; answer key (keep away from listeners) -> {os.path.dirname(a.out)}/listening_key/")


if __name__ == "__main__":
    main()
