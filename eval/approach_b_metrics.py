"""Approach A vs B on the same 5 prompts at 30 s (main venv).

    python eval/approach_b_metrics.py --b out/approach_b --a out/approach_a30
    eval/.venv/bin/python eval/clap_score.py --batch out/approach_a30 > eval/results/clap_a30.md
    python eval/approach_b_metrics.py --report > eval/results/approach_comparison.md

Step 1 renders Approach A (this engine, local pipeline, real FluidSynth) for the prompts in approach_b.py and
measures both A and B with the same QA functions; step 3 prints the comparison table.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

RESULTS = os.path.join(os.path.dirname(__file__), "results", "approach_metrics.json")


def measure(d: str, expected_s: float) -> dict:
    import glob

    from musicengine import mixdown, qa

    mix, sr = mixdown.read_wav(os.path.join(d, "mix.wav"))
    stems = {os.path.basename(p)[:-4]: mixdown.read_wav(p)[0] for p in sorted(glob.glob(os.path.join(d, "stems", "*.wav")))}
    n = min(len(mix), *(len(v) for v in stems.values()))
    stems_n = {k: v[:n] for k, v in stems.items()}
    return {"length_s": round(len(mix) / sr, 4), "length_error_s": round(abs(len(mix) / sr - expected_s), 4),
            "lufs": round(qa.integrated_lufs(mix, sr), 2), "true_peak_dbtp": round(qa.true_peak_dbtp(mix), 2),
            "sum_diff_db": round(qa.sum_diff_db(list(stems_n.values()), mix[:n]), 1),
            "bleed_max_explained_db": qa.stem_bleed(stems_n, sr)["max_explained_db"],
            "max_abs_xcorr": round(max(abs(v) for v in qa.stem_bleed(stems_n, sr)["pairwise_xcorr"].values()), 3),
            "spectral_overlap": qa.spectral_overlap(stems_n, sr)["mean_overlap"], "stems": list(stems)}


def run(a_dir: str, b_dir: str):
    from musicengine.config import Settings
    from musicengine.schemas import MusicRequest
    from musicengine.worker.pipeline import run_generate

    b = json.load(open(os.path.join(b_dir, "results.json")))
    out = {"A": {}, "B": {}, "B_meta": {k: v for k, v in b.items() if k != "cases"}}
    s = Settings(renderer="fluidsynth")
    for case, info in b["cases"].items():
        d = os.path.join(a_dir, case)
        os.makedirs(d, exist_ok=True)
        req = MusicRequest(prompt=info["prompt"], duration_s=b["requested_s"], seed=1)
        t0 = time.perf_counter()
        res = run_generate(f"a30-{case}", req, d, s)
        wall = time.perf_counter() - t0
        json.dump(req.model_dump(mode="json"), open(os.path.join(d, "request.json"), "w"))
        json.dump(res["manifest"], open(os.path.join(d, "music_manifest.json"), "w"))
        out["A"][case] = {"prompt": info["prompt"], "generate_s": round(wall, 2),
                          "compute_s": res["manifest"]["cost"]["compute_seconds"], **measure(d, b["requested_s"])}
        out["B"][case] = {**info, **measure(os.path.join(b_dir, case), b["requested_s"])}
        print(case, "A", out["A"][case]["generate_s"], "B", info["generate_s"] + info["separate_s"], flush=True)
    json.dump(out, open(RESULTS, "w"), indent=2)


def report():
    import statistics as st

    r = json.load(open(RESULTS))
    clap_a = {}
    p = os.path.join(os.path.dirname(RESULTS), "clap_a30.md")
    if os.path.exists(p):
        for line in open(p):
            m = re.match(r"\| (\w+) \| .* \| (-?[\d.]+) \| (-?[\d.]+) \| \d+/\d+ \|", line)
            if m:
                clap_a[m.group(1)] = float(m.group(2))
    cases = list(r["B"])

    def mean(side, k):
        vals = [r[side][c][k] for c in cases if r[side][c].get(k) is not None]
        return st.mean(vals) if vals else float("nan")

    a_sec = mean("A", "generate_s")
    b_sec = st.mean(r["B"][c]["generate_s"] + r["B"][c]["separate_s"] for c in cases)
    D = r["B_meta"]["requested_s"]
    print(f"Same {len(cases)} prompts, {D} s each, same machine ({r['B_meta']['device']}, torch {r['B_meta']['torch']}).\n")
    print("| metric | A: symbolic + FluidSynth (this engine) | B: MusicGen-small + Demucs |")
    print("|---|---|---|")
    print(f"| CLAP prompt match (mean cos, laion/clap-htsat-unfused) | "
          f"{st.mean(clap_a.values()):.3f} | {mean('B', 'clap'):.3f} |" if clap_a else "| CLAP | (run clap_a30) | |")
    print(f"| wall seconds per 30 s clip | {a_sec:.1f} | {b_sec:.1f} (generate {mean('B', 'generate_s'):.1f} + "
          f"separate {mean('B', 'separate_s'):.1f}) |")
    print(f"| seconds per 60 s of music | {a_sec * 60 / D:.1f} | {b_sec * 60 / D:.1f} |")
    print(f"| length error vs requested | {max(r['A'][c]['length_error_s'] for c in cases):.4f} s (max) | "
          f"{max(r['B'][c]['length_error_s'] for c in cases):.4f} s (max); no bar-aligned ending control |")
    print(f"| stems | 4 rendered parts (drums, bass, harmony, melody) | 4 separated estimates "
          f"({', '.join(r['B'][cases[0]]['stems'])}) |")
    print(f"| stem sum vs mix | {mean('A', 'sum_diff_db'):.1f} dB | {mean('B', 'sum_diff_db'):.1f} dB |")
    print(f"| max abs waveform xcorr between stems | {mean('A', 'max_abs_xcorr'):.3f} | {mean('B', 'max_abs_xcorr'):.3f} |")
    print(f"| shared-content index (NNLS explained, dB) | {mean('A', 'bleed_max_explained_db'):.1f} | "
          f"{mean('B', 'bleed_max_explained_db'):.1f} |")
    print(f"| loudness before mastering | mastered to -16.0 LUFS | {mean('B', 'lufs'):.1f} LUFS raw (needs mastering) |")
    print("| licence for commercial use | owned code + MIT SoundFont + permissive libs | **MusicGen weights "
          "CC-BY-NC-4.0: non-commercial only**; Demucs MIT |")
    print("| API fees | 0 | 0 (self-hosted); GPU rental otherwise |")
    print("\nPer-case numbers: `eval/results/approach_metrics.json`.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="out/approach_a30")
    ap.add_argument("--b", default="out/approach_b")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    report() if args.report else run(args.a, args.b)
