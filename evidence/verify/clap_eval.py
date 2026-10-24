"""CLAP prompt match for the evidence run (run with eval/.venv/bin/python; HF_HOME=eval/.cache).
Matched = cos(audio, own prompt); control = the same audio against every other prompt of the set."""
import csv
import glob
import json
import os
import statistics
import sys

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly
from transformers import ClapModel, ClapProcessor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODEL = "laion/clap-htsat-unfused"


def windows(path, n=6):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    m = x.mean(axis=1)
    if sr != 48000:
        m = resample_poly(m, 48000, sr).astype(np.float32)
    w = 480000
    if len(m) <= w:
        return [m]
    return [m[s:s + w] for s in np.linspace(0, len(m) - w, min(n, int(np.ceil(len(m) / w)))).astype(int)]


def main(run_id):
    runs = os.path.join(ROOT, "evidence", "runs", run_id)
    audio = os.path.join(ROOT, "out", "evidence", run_id)
    items = []
    for d in sorted(glob.glob(os.path.join(runs, "core_*"))):
        name = os.path.basename(d)
        items.append((name, json.load(open(os.path.join(d, "request.json")))["prompt"], os.path.join(audio, name, "mix.wav")))
    model = ClapModel.from_pretrained(MODEL).eval()
    proc = ClapProcessor.from_pretrained(MODEL)
    prompts = [p for _, p, _ in items]
    with torch.no_grad():
        t = proc(text=prompts, return_tensors="pt", padding=True)
        T = torch.nn.functional.normalize(model.get_text_features(**t), dim=-1).numpy()
        rows, ctrl = [], []
        for i, (name, prompt, path) in enumerate(items):
            f = proc(audios=windows(path), sampling_rate=48000, return_tensors="pt")
            e = torch.nn.functional.normalize(model.get_audio_features(**f), dim=-1).mean(0)
            e = torch.nn.functional.normalize(e, dim=-1).numpy()
            sims = T @ e
            others = [float(s) for j, s in enumerate(sims) if j != i]
            rank = 1 + int(np.sum(sims > sims[i]))
            rows.append({"case": name, "prompt": prompt, "clap_matched": round(float(sims[i]), 4),
                         "clap_mismatched_mean": round(statistics.mean(others), 4), "rank_of_own_prompt": rank,
                         "n_prompts": len(prompts)})
            for j, s in enumerate(sims):
                if j != i:
                    ctrl.append({"audio_case": name, "other_prompt": prompts[j], "clap": round(float(s), 4)})
    out = os.path.join(ROOT, "evidence", "eval")
    os.makedirs(out, exist_ok=True)
    for fname, data in (("clap.csv", rows), ("control_clap.csv", ctrl)):
        with open(os.path.join(out, fname), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    import transformers

    json.dump({"model": MODEL, "licence": "Apache-2.0", "transformers": transformers.__version__, "torch": torch.__version__,
               "device": "cpu", "n": len(rows)}, open(os.path.join(out, "clap_meta.json"), "w"), indent=2)
    print("clap", statistics.mean(r["clap_matched"] for r in rows), statistics.mean(r["clap_mismatched_mean"] for r in rows))


if __name__ == "__main__":
    main(sys.argv[1])
