"""Prompt match with an independent model: LAION CLAP (laion/clap-htsat-unfused, Apache-2.0, via transformers).
Evaluation only (separate venv `eval/requirements.txt`, never in the service image).

laion/larger_clap_music was tried first, but its text tower returns the same embedding for every text
(cosine 1.00 between "jazz music" and "birds chirping") under transformers 4.46 and 5.20, so it cannot score
prompt match; the general HTSAT checkpoint discriminates (sanity check in eval/README.md).

    eval/.venv/bin/python eval/clap_score.py --batch out/batch3 --baseline-from out/listening_pack \
        > eval/results/clap.md

Per case: cosine(audio, own prompt) vs mean cosine(audio, other prompts) (mismatched control), and the rank
of the own prompt among all prompts (retrieval). Audio embedding = mean over up to 6 x 10 s windows.
"""
import argparse
import glob
import json
import os
import statistics

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly
from transformers import ClapModel, ClapProcessor

MODEL = "laion/clap-htsat-unfused"
SKIP = ("hard_non_english", "hard_unknown_language", "hard_vague", "err_")


def load_windows(path, sr_target=48000, win_s=10, max_windows=6):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    m = x.mean(axis=1)
    if sr != sr_target:
        m = resample_poly(m, sr_target, sr).astype(np.float32)
    w = win_s * sr_target
    if len(m) <= w:
        return [m]
    starts = np.linspace(0, len(m) - w, min(max_windows, int(np.ceil(len(m) / w)))).astype(int)
    return [m[s:s + w] for s in starts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="out/batch3")
    ap.add_argument("--baseline-from", default="")
    a = ap.parse_args()
    dev = "cpu"  # MPS lacks upsample_bicubic2d used by HTSAT; CPU is fast enough for ~50 clips
    model = ClapModel.from_pretrained(MODEL).to(dev).eval()
    proc = ClapProcessor.from_pretrained(MODEL)

    cases = []
    for man in sorted(glob.glob(os.path.join(a.batch, "*", "music_manifest.json"))):
        name = os.path.basename(os.path.dirname(man))
        if name.startswith(SKIP):
            continue
        req = json.load(open(os.path.join(os.path.dirname(man), "request.json")))
        cases.append((name, req["prompt"], os.path.join(os.path.dirname(man), "mix.wav")))
    prompts = sorted({p for _, p, _ in cases})

    def _vec(out):
        """transformers >= 5 returns an output object; older versions a tensor."""
        if isinstance(out, torch.Tensor):
            return out
        for k in ("text_embeds", "audio_embeds", "pooler_output"):
            if getattr(out, k, None) is not None:
                return getattr(out, k)
        raise TypeError(type(out))

    @torch.no_grad()
    def text_emb(texts):
        t = proc(text=texts, return_tensors="pt", padding=True).to(dev)
        e = _vec(model.get_text_features(**t))
        return torch.nn.functional.normalize(e, dim=-1).cpu().numpy()

    @torch.no_grad()
    def audio_emb(path):
        wins = load_windows(path)
        f = proc(audios=wins, sampling_rate=48000, return_tensors="pt").to(dev)
        e = torch.nn.functional.normalize(_vec(model.get_audio_features(**f)), dim=-1).mean(0)
        return torch.nn.functional.normalize(e, dim=-1).cpu().numpy()

    T = text_emb(prompts)
    idx = {p: i for i, p in enumerate(prompts)}
    rows = []
    for name, prompt, path in cases:
        e = audio_emb(path)
        sims = T @ e
        own = float(sims[idx[prompt]])
        others = [float(s) for j, s in enumerate(sims) if j != idx[prompt]]
        rank = 1 + int(np.sum(sims > own))
        rows.append((name, prompt, own, statistics.mean(others), rank))

    import transformers

    print(f"Model `{MODEL}` (Apache-2.0), transformers {transformers.__version__}, torch {torch.__version__}, "
          f"device {dev}, {len(rows)} outputs, {len(prompts)} distinct prompts.\n")
    print("| case | prompt | cos(audio, own prompt) | mean cos(audio, other prompts) | rank of own prompt |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1][:60]} | {r[2]:.3f} | {r[3]:.3f} | {r[4]}/{len(prompts)} |")
    own = [r[2] for r in rows]
    other = [r[3] for r in rows]
    ranks = [r[4] for r in rows]
    print(f"\n**Matched** mean {statistics.mean(own):.3f} (sd {statistics.pstdev(own):.3f}); **mismatched control** "
          f"mean {statistics.mean(other):.3f} (sd {statistics.pstdev(other):.3f}); matched > control in "
          f"{sum(o > c for o, c in zip(own, other))}/{len(rows)}. Retrieval: top-1 {sum(r == 1 for r in ranks)}/{len(rows)}, "
          f"top-3 {sum(r <= 3 for r in ranks)}/{len(rows)}, chance top-1 = {1 / len(prompts):.2f}.")

    if a.baseline_from and os.path.exists(os.path.join(a.baseline_from, "..", "listening_key", "answer_key.csv")):
        import csv

        key = list(csv.DictReader(open(os.path.join(a.baseline_from, "..", "listening_key", "answer_key.csv"))))
        print("\n### Ours vs baseline (piano loop) on the listening-test prompts\n")
        print("| prompt | ours | baseline |")
        print("|---|---|---|")
        wins = 0
        for k in key:
            t = text_emb([k["prompt"]])[0]
            base_label = "B" if k["ours"] == "A" else "A"
            s_ours = float(audio_emb(os.path.join(a.baseline_from, f"pair{int(k['pair']):02d}_{k['ours']}.wav")) @ t)
            s_base = float(audio_emb(os.path.join(a.baseline_from, f"pair{int(k['pair']):02d}_{base_label}.wav")) @ t)
            wins += s_ours > s_base
            print(f"| {k['prompt'][:60]} | {s_ours:.3f} | {s_base:.3f} |")
        print(f"\nOurs scores higher than the baseline on {wins}/{len(key)} prompts.")


if __name__ == "__main__":
    main()
