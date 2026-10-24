"""E5: listening clips, spectrograms, listening/log.csv template, demo/demo_script.md."""
import os
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.signal import spectrogram  # noqa: E402

from common import EV, audio_files, cases, out_dir, read, rel, to_mp3, write_csv  # noqa: E402

L = out_dir("listening")
C = out_dir("listening", "clips")


def clips():
    rows = []
    # last 3 s of 10 outputs + every section change (made by must_haves.py), linked here
    for src, kind in (("must_haves/mh1_length/last3s", "ending"), ("must_haves/mh5_audio/section_change_clips", "section_change")):
        dst = os.path.join(C, kind)
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(os.path.join(EV, src), dst)
        for f in sorted(os.listdir(dst)):
            rows.append({"run": f.split("_s")[0] if kind == "section_change" else f[:-4], "check": kind,
                         "clip": rel(os.path.join(dst, f)), "rating/pass": "", "notes": "", "listener": ""})
    # every stem solo (10 s from the middle) and the full mix for each core prompt + spectrograms
    for c in cases("core_"):
        f = audio_files(c)
        mix, sr = read(f["mix.wav"])
        mid = len(mix) // 2
        for k, p in f.items():
            if not k.endswith(".wav"):
                continue
            x, _ = read(p)
            name = k.replace("stems/", "stem_").replace(".wav", "")
            path = to_mp3(x[mid - 5 * sr: mid + 5 * sr], sr, os.path.join(C, "stems", f"{c['name']}_{name}.mp3"), kbps=96)
            rows.append({"run": c["name"], "check": "stem_solo" if "stem_" in name else "mix_excerpt", "clip": rel(path),
                         "rating/pass": "", "notes": "", "listener": ""})
        rows.append({"run": c["name"], "check": "prompt_match", "clip": rel(f["mix.wav"]),
                     "rating/pass": "", "notes": f"prompt: {c['request']['prompt']} (rate: matches / partly / no)",
                     "listener": ""})
        rows.append({"run": c["name"], "check": "vocals_free", "clip": rel(f["mix.wav"]), "rating/pass": "",
                     "notes": "any voice, singing or words? (pass / fail)", "listener": ""})
        fr, t, S = spectrogram(mix.mean(axis=1), fs=sr, nperseg=2048, noverlap=1024)
        fig, ax = plt.subplots(figsize=(8, 2.6))
        ax.pcolormesh(t, fr, 10 * np.log10(S + 1e-12), shading="auto", cmap="magma", vmin=-120, vmax=-30)
        ax.set_ylim(0, 12000)
        ax.set_title(f"{c['name']}: spectrogram (0-12 kHz)", fontsize=8)
        ax.tick_params(labelsize=7)
        fig.tight_layout()
        os.makedirs(os.path.join(C, "spectrograms"), exist_ok=True)
        fig.savefig(os.path.join(C, "spectrograms", f"{c['name']}.png"), dpi=100)
        plt.close(fig)
    log = os.path.join(L, "log.csv")
    if not os.path.exists(log):  # never overwrite human ratings
        write_csv(log, rows, ["run", "check", "clip", "rating/pass", "notes", "listener"])
    open(os.path.join(L, "README.md"), "w").write(
        "# Listening checks (human)\n\nOpen `log.csv` and, for every row, listen to `clip` and fill `rating/pass`, "
        "`notes` and `listener`.\n\n| check | what to listen for | value |\n|---|---|---|\n"
        "| ending | ends on purpose (final hit or fade), no hard cut | pass / fail |\n"
        "| section_change | change is audible, on the beat, no click or gap | pass / fail |\n"
        "| stem_solo / mix_excerpt | each stem is one clear part; no clicks | pass / fail |\n"
        "| prompt_match | does the full mix obviously match the prompt in `notes`? | matches / partly / no |\n"
        "| vocals_free | no voice, singing or spoken words | pass / fail |\n\n"
        "Full WAVs are in `out/evidence/<run>/` (and `audio-pack.zip`). Re-run `make evidence-form` afterwards.\n")
    print(len(rows), "listening rows")


def demo_script():
    d = out_dir("demo")
    open(os.path.join(d, "demo_script.md"), "w").write("""# Demo video script (<= 8 min, one take, unedited)

Record the screen and terminal. Replace each `VIDEO@` placeholder in `evidence/form_inputs.yaml` with the real
`mm:ss` after recording; the form filler copies them into the evidence cells.

| Target | Placeholder | Do | Expected |
|---|---|---|---|
| 00:00 | VIDEO@intro | `git log --oneline \\| head -3`, `curl -s $DEMO/health` | `git_sha` equals the tag `submission-v1` |
| 00:30 | VIDEO@clean_run | Web UI: example "Calm cinematic piano...", 45 s, Generate | progress steps, then the mix, 4 stems, timeline, facts (-16.0 LUFS, -1.6 dBTP) |
| 02:00 | VIDEO@stems | Play two stems solo; download the manifest; show `stems[]`, `beats`, `loudness`, `ai_generated` | stems are separate parts; manifest fields present |
| 02:45 | VIDEO@regen | Click Regenerate on Drums | new version; the other three stems are byte-identical (`evidence/levels/adv_regen/hash_compare.txt`) |
| 03:30 | VIDEO@failure | `curl -X POST $DEMO/api/v1/music/jobs -d '{"prompt":"x","duration_s":400}'` and a vocals prompt in the UI | 422 VALIDATION_ERROR JSON; the vocals job succeeds with a VOCALS_NOT_SUPPORTED note |
| 04:15 | VIDEO@fallback | Locally: `FAULT_INJECT=render_primary_fail` worker, one job | job succeeds with PROVIDER_FALLBACK_USED; manifest renderer = numpy |
| 05:00 | VIDEO@tests | `make test` (or `pytest tests`) | all tests pass, no API keys |
| 06:30 | VIDEO@design | Open `src/musicengine/mixdown.py::master` and `planner/timegrid.py` | explain: one limiter curve from the sum applied to every stem, so mix = sum of stems; length planned in whole bars |
| 07:45 | VIDEO@end | Close | |
""")


if __name__ == "__main__":
    clips()
    demo_script()
