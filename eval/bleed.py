"""Stem cleanliness report over a batch output directory, with a band-split control.

    python eval/bleed.py out/batch2 > eval/results/bleed.md

Metrics (see musicengine.qa):
  explained_db     - share of a stem's STFT magnitude explained by an NNLS fit onto the other stems.
                     Note: this measures *shared musical content* (same key, same rhythm), not leakage;
                     it does NOT separate real stems from EQ bands (the control below scores lower).
  max |xcorr|      - waveform cross-correlation between stems (leakage would show up here).
  spectral_overlap - mean share of each stem's spectrum shared with another stem (band-split detector).
  sum_diff_db      - mix minus the sum of stems.
"""
import glob
import json
import os
import sys

import numpy as np
from scipy.signal import butter, sosfilt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from musicengine import mixdown, qa  # noqa: E402


def band_split(mix, sr):
    sos = [butter(4, 200, "lowpass", fs=sr, output="sos"), butter(4, [200, 2000], "bandpass", fs=sr, output="sos"),
           butter(4, 2000, "highpass", fs=sr, output="sos")]
    return {n: sosfilt(s, mix, axis=0) for n, s in zip(("low", "mid", "high"), sos)}


def main(root):
    rows = []
    for man in sorted(glob.glob(os.path.join(root, "*", "music_manifest.json"))):
        d = os.path.dirname(man)
        m = json.load(open(man))
        sr = m["sample_rate"]
        stems = {os.path.basename(p)[:-4]: mixdown.read_wav(p)[0] for p in sorted(glob.glob(f"{d}/stems/*.wav"))}
        mix, _ = mixdown.read_wav(f"{d}/mix.wav")
        b, o = qa.stem_bleed(stems, sr), qa.spectral_overlap(stems, sr)
        cb, co = qa.stem_bleed(band_split(mix, sr), sr), qa.spectral_overlap(band_split(mix, sr), sr)
        rows.append((os.path.basename(d), m["style"], b["max_explained_db"],
                     max(abs(v) for v in b["pairwise_xcorr"].values()), o["mean_overlap"],
                     qa.sum_diff_db(list(stems.values()), mix), cb["max_explained_db"], co["mean_overlap"]))
    print("| case | style | stems: max explained dB | stems: max abs xcorr | stems: spectral overlap | sum diff dB "
          "| band-split control: max explained dB | control: spectral overlap |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]:.1f} | {r[3]:.3f} | {r[4]:.2f} | {r[5]:.1f} | {r[6]:.1f} | {r[7]:.2f} |")
    a = np.array([r[2:] for r in rows], dtype=float)
    print(f"\n**n = {len(rows)}.** Mean over cases: explained {a[:, 0].mean():.1f} dB, max |xcorr| {a[:, 1].mean():.3f}, "
          f"spectral overlap {a[:, 2].mean():.2f} (band-split control {a[:, 5].mean():.2f}; overlap higher than control "
          f"in {int(np.sum(a[:, 2] > a[:, 5]))}/{len(rows)} cases), sum diff {a[:, 3].mean():.1f} dB "
          f"(worst {a[:, 3].max():.1f}).")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
