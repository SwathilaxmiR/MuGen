"""Approach B (comparison only): text-to-music model + source separation.

    HF_HOME=eval/.cache eval/.venv/bin/python eval/approach_b.py --out out/approach_b

MusicGen-small (facebook/musicgen-small, weights CC-BY-NC-4.0 = non-commercial) generates 30 s from the
prompt; Demucs htdemucs (MIT) splits it into drums/bass/other/vocals. Timings, the requested vs actual
length, and CLAP prompt match (laion/clap-htsat-unfused) are written to out/approach_b/results.json.
Audio QA (LUFS, sum-difference, bleed) is computed by eval/approach_b_metrics.py in the main venv.
"""
import argparse
import json
import os
import time

import numpy as np
import soundfile as sf
import torch

PROMPTS = {
    "p01_cinematic": "Epic cinematic orchestral score that builds to a heroic climax",
    "p02_lofi": "chill lo-fi beats for studying late at night",
    "p04_electronic": "energetic EDM festival track with a big drop",
    "p06_tense": "tense suspense thriller underscore, dark and ominous",
    "p11_jazz": "smooth jazz lounge with saxophone",
}
DURATION_S = 30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/approach_b")
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    from transformers import AutoProcessor, ClapModel, ClapProcessor, MusicgenForConditionalGeneration

    t0 = time.perf_counter()
    proc = AutoProcessor.from_pretrained("facebook/musicgen-small")
    mg = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small").to(a.device).eval()
    load_s = time.perf_counter() - t0
    sr = mg.config.audio_encoder.sampling_rate
    frame_rate = mg.config.audio_encoder.frame_rate
    max_new = int(DURATION_S * frame_rate)

    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    t0 = time.perf_counter()
    sep = get_model("htdemucs").to(a.device).eval()
    sep_load_s = time.perf_counter() - t0

    clap = ClapModel.from_pretrained("laion/clap-htsat-unfused").eval()
    cproc = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")
    results = {"model": "facebook/musicgen-small", "separator": "htdemucs", "device": a.device,
               "torch": torch.__version__, "model_load_s": round(load_s, 2), "separator_load_s": round(sep_load_s, 2),
               "requested_s": DURATION_S, "cases": {}}
    for case, prompt in PROMPTS.items():
        d = os.path.join(a.out, case)
        os.makedirs(os.path.join(d, "stems"), exist_ok=True)
        inputs = proc(text=[prompt], padding=True, return_tensors="pt").to(a.device)
        torch.manual_seed(0)
        t0 = time.perf_counter()
        with torch.no_grad():
            audio = mg.generate(**inputs, do_sample=True, max_new_tokens=max_new)
        gen_s = time.perf_counter() - t0
        wav = audio[0, 0].cpu().numpy().astype(np.float32)
        sf.write(os.path.join(d, "mix_raw.wav"), wav, sr)
        # Demucs expects 44.1 kHz stereo
        import torchaudio.functional as AF

        x = torch.from_numpy(wav)[None].repeat(2, 1)
        x44 = AF.resample(x, sr, sep.samplerate)
        t0 = time.perf_counter()
        with torch.no_grad():
            stems = apply_model(sep, x44[None].to(a.device), split=True, overlap=0.25, progress=False)[0].cpu()
        sep_s = time.perf_counter() - t0
        sf.write(os.path.join(d, "mix.wav"), x44.T.numpy(), sep.samplerate)
        for name, s in zip(sep.sources, stems):
            sf.write(os.path.join(d, "stems", f"{name}.wav"), s.T.numpy(), sep.samplerate)
        with torch.no_grad():
            t = cproc(text=[prompt], return_tensors="pt", padding=True)
            te = torch.nn.functional.normalize(clap.get_text_features(**t), dim=-1)
            x48 = AF.resample(torch.from_numpy(wav)[None], sr, 48000)[0].numpy()
            wins = [x48[i:i + 480000] for i in range(0, max(1, len(x48) - 480000 + 1), 480000)][:6] or [x48]
            f = cproc(audios=wins, sampling_rate=48000, return_tensors="pt")
            ae = torch.nn.functional.normalize(clap.get_audio_features(**f), dim=-1).mean(0)
            ae = torch.nn.functional.normalize(ae, dim=-1)
        results["cases"][case] = {"prompt": prompt, "generate_s": round(gen_s, 2), "separate_s": round(sep_s, 2),
                                  "actual_s": round(len(wav) / sr, 4),
                                  "length_error_s": round(abs(len(wav) / sr - DURATION_S), 4),
                                  "clap": round(float(ae @ te[0]), 4), "sources": list(sep.sources)}
        print(case, results["cases"][case], flush=True)
    with open(os.path.join(a.out, "results.json"), "w") as fh:
        json.dump(results, fh, indent=2)


if __name__ == "__main__":
    main()
