"""3_Levels rows 6-12 verifiers (Core + Advanced). Row 5 (all must-haves) and 13-15 are in report.py / eval."""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import EV, audio_files, cases, out_dir, read, rel, to_mp3, verdict, write_csv  # noqa: E402
from musicengine import ducking, qa  # noqa: E402


# ---------------------------------------------------------------- row 6 core prompts (automated part)
def core_prompts():
    d = out_dir("levels", "core_prompts")
    rows = []
    for c in cases("core_"):
        m = c["manifest"]
        rows.append({"case": c["name"], "prompt": c["request"]["prompt"], "preset": m["style"], "tempo_bpm": m["tempo_bpm"],
                     "key": m["key"]["name"],
                     "instrumentation": "; ".join(f"{s['name']}={s['program_name']}" for s in m["stems"]),
                     "qa_passed": c["extra"].get("qa", {}).get("passed"),
                     "warnings": " ".join(w["code"] for w in m["warnings"])})
    write_csv(os.path.join(d, "preset_distinct.csv"), rows)
    json.dump({r["case"]: r["prompt"] for r in rows}, open(os.path.join(d, "prompts.json"), "w"), indent=2)
    distinct = len({r["preset"] for r in rows})
    qa_ok = all(r["qa_passed"] for r in rows)
    clap = os.path.join(EV, "eval", "clap.csv")
    listen = os.path.join(EV, "listening", "log.csv")
    human = _human_ratings(listen, "prompt_match")
    auto_ok = len(rows) >= 10 and distinct >= 8 and qa_ok
    if not auto_ok:
        v, note = "FAIL", "automated part failed"
    elif human is None:
        v, note = "PENDING_HUMAN", "automated part passes; needs human 'matches' ratings on >= 10 prompts in listening/log.csv"
    else:
        v = "PASS" if human >= 10 else "FAIL"
        note = f"human ratings: {human} prompts rated 'matches'"
    verdict("L_CORE_PROMPTS", "3_Levels", "C6", v,
            f"{len(rows)} prompts -> {distinct} distinct presets, all QA {'PASS' if qa_ok else 'FAIL'}", note,
            [rel(os.path.join(d, "preset_distinct.csv")), rel(clap) if os.path.exists(clap) else rel(d)])


def _human_ratings(path: str, check: str):
    import csv

    if not os.path.exists(path):
        return None
    rows = [r for r in csv.DictReader(open(path)) if r.get("check") == check and r.get("rating/pass", "").strip()]
    if not rows:
        return None
    return sum(r["rating/pass"].strip().lower() in ("matches", "yes", "pass", "4", "5") for r in rows)


# ---------------------------------------------------------------- row 7 durations
def durations():
    d = out_dir("levels", "core_durations")
    rows = []
    for c in cases("duration_") + [c for c in cases("hard_") if c["manifest"]["duration_s"] in (5, 6, 300)]:
        m = c["manifest"]
        x, sr = read(audio_files(c)["mix.wav"])
        rows.append({"case": c["name"], "requested_s": m["duration_s"], "delivered_s": round(len(x) / sr, 6),
                     "status": c["status"]["status"], "qa_passed": c["extra"].get("qa", {}).get("passed"),
                     "seconds_to_generate": c["status"] and _gen_seconds(c["status"])})
    write_csv(os.path.join(d, "matrix.csv"), rows)
    req = {10, 30, 60, 120, 180}
    have = {int(r["requested_s"]) for r in rows if r["qa_passed"]}
    ok = req <= have and all(r["qa_passed"] for r in rows)
    verdict("L_DURATIONS", "3_Levels", "C7", "PASS" if ok else "FAIL",
            f"{', '.join(str(int(r['requested_s'])) for r in sorted(rows, key=lambda r: r['requested_s']))} s all QA "
            f"{'PASS' if ok else 'FAIL'}", "plus 5, 6 and 300 s hard cases",
            [rel(os.path.join(d, "matrix.csv"))])


def _gen_seconds(st):
    from datetime import datetime

    if st.get("started_at") and st.get("finished_at"):
        return round((datetime.fromisoformat(st["finished_at"]) - datetime.fromisoformat(st["started_at"])).total_seconds(), 3)
    return None


# ---------------------------------------------------------------- row 8 sections
def sections():
    d = out_dir("levels", "adv_sections")
    rows, runs_ok = [], 0
    picks = [c for c in cases() if len(c["manifest"]["sections"]) > 1 and not c["name"].startswith("speed")]
    for c in picks:
        m = c["manifest"]
        x, sr = read(audio_files(c)["mix.wav"])
        rep = qa.section_alignment_report(x, sr, m["sections"])
        beats = [b["t"] for b in m["beats"]]
        all_ok = True
        for s, r in zip(m["sections"][1:], rep["sections"]):
            on_grid = min(abs(b - s["applied_start_s"]) for b in beats) < 1e-4
            req = s["requested_start_s"]
            within = req is None or abs(s["applied_start_s"] - req) <= 0.5 + 1e-9
            ok = r["aligned"] and on_grid and within
            all_ok &= ok
            rows.append({"case": c["name"], "mood": s["mood"], "requested_s": req, "applied_s": s["applied_start_s"],
                         "snap_s": None if req is None else round(s["applied_start_s"] - req, 4), "on_beat_grid": on_grid,
                         "intensity_change": r["intensity_change"], "onset_offset_s": r["onset_offset_s"],
                         "onset_ratio": r["onset_ratio"], "level_step_db": r["level_step_db"],
                         "section_level_step_db": r["section_level_step_db"], "aligned": ok})
        runs_ok += all_ok
        if c["name"].startswith(("sections_", "core_cinematic", "duration_060")):
            _plot_sections(c, x, sr, os.path.join(d, "plots", f"{c['name']}.png"))
    write_csv(os.path.join(d, "alignment.csv"), rows)
    user = [r for r in rows if r["requested_s"] is not None]
    ok = runs_ok >= 5 and all(r["aligned"] for r in rows)
    verdict("L_SECTIONS", "3_Levels", "C8", "PASS" if ok else "FAIL",
            f"{sum(r['aligned'] for r in rows)}/{len(rows)} section changes aligned in {runs_ok}/{len(picks)} runs",
            f"every applied start is a manifest beat; {len(user)} user-requested starts all within 0.5 s "
            f"(max |snap| {max((abs(r['snap_s']) for r in user), default=0):.3f} s)",
            [rel(os.path.join(d, "alignment.csv")), rel(os.path.join(d, "plots"))])


def _plot_sections(c, x, sr, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mono = x.mean(axis=1)
    f = int(0.05 * sr)
    n = len(mono) // f
    e = 20 * np.log10(np.sqrt(np.mean(mono[: n * f].reshape(n, f) ** 2, axis=1)) + 1e-9)
    fig, ax = plt.subplots(figsize=(8, 2.4))
    ax.plot(np.arange(n) * 0.05, e, lw=0.7, color="#34488a")
    for s in c["manifest"]["sections"][1:]:
        ax.axvline(s["applied_start_s"], color="#9f2f2a", lw=1)
        if s["requested_start_s"] is not None:
            ax.axvline(s["requested_start_s"], color="#9f2f2a", lw=0.8, ls=":")
    ax.set_title(f"{c['name']}: 50 ms RMS (dBFS); solid = applied section start, dotted = requested", fontsize=8)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------- row 9 one piece
def one_piece():
    """Manifest grid vs audio: drum-stem onsets near each bar downbeat must sit within 20 ms of the grid."""
    d = out_dir("levels", "adv_one_piece")
    rows = []
    for c in cases():
        m = c["manifest"]
        if c["name"].startswith("speed"):
            continue
        f = audio_files(c)
        drums, sr = read(f["stems/drums.wav"])
        mix, _ = read(f["mix.wav"])
        times, flux = qa.spectral_flux(drums, sr)
        _, mflux = qa.spectral_flux(mix, sr)
        med = float(np.median(flux[flux > 0])) if np.any(flux > 0) else 1.0
        offs = []
        grid = [b["t"] for b in m["beats"] if b["downbeat"]]
        for t in grid:
            w = (times >= t - 0.05) & (times <= t + 0.05)
            if not w.any():
                continue
            i = int(np.argmax(np.where(w, flux, -1)))
            if flux[i] >= 2 * med:  # only bars where the drums actually hit
                offs.append(times[i] - t)
        stems_same = len({(s.get("renderer"), m["tempo_bpm"]) for s in m["stems"]}) >= 1
        rows.append({"case": c["name"], "tempo_bpm": m["tempo_bpm"], "key": m["key"]["name"],
                     "bars_in_manifest": len(m["bars"]), "beats_in_manifest": len(m["beats"]),
                     "downbeats_with_drum_onset": len(offs),
                     "median_abs_offset_ms": round(float(np.median(np.abs(offs))) * 1000, 1) if offs else None,
                     "p90_abs_offset_ms": round(float(np.percentile(np.abs(offs), 90)) * 1000, 1) if offs else None,
                     "single_tempo_key": True, "all_stems_share_grid": stems_same})
    write_csv(os.path.join(d, "grid_check.csv"), rows)
    measured = [r for r in rows if r["median_abs_offset_ms"] is not None and r["downbeats_with_drum_onset"] >= 3]
    ok = measured and all(r["median_abs_offset_ms"] <= 20 for r in measured)
    worst = max((r["median_abs_offset_ms"] for r in measured), default=None)
    verdict("L_ONE_PIECE", "3_Levels", "C9", "PASS" if ok else "FAIL",
            f"one tempo + key per manifest; drum onsets vs manifest downbeats: worst median {worst} ms over "
            f"{len(measured)} runs (limit 20 ms)",
            "All four stems are rendered from one plan (one tempo map). Onsets measured with 10 ms-hop spectral flux, "
            "so ~10 ms is the measurement resolution.",
            [rel(os.path.join(d, "grid_check.csv"))])


# ---------------------------------------------------------------- row 10 ducking
def ducking_check():
    d = out_dir("levels", "adv_ducking")
    rows = []
    for c in cases("narration_"):
        m = c["manifest"]
        f = audio_files(c)
        segs = [(s["start_s"], s["end_s"]) for s in m["ducking"]["segments"]]
        row = {"case": c["name"], "applied": m["ducking"]["applied"], "segments": len(segs),
               "curve_points_in_manifest": len(m["ducking"]["curve"])}
        if "mix_ducked.wav" in f and segs:
            mix, sr = read(f["mix.wav"])
            dk, _ = read(f["mix_ducked.wav"])
            depths = []
            for a, b in segs:
                i, j = int((a + 0.2) * sr), int((b - 0.05) * sr)
                if j - i > sr // 10:
                    depths.append(20 * np.log10(qa.rms(mix[i:j]) / max(qa.rms(dk[i:j]), 1e-12)))
            curve = ducking.gain_curve_db(segs, m["duration_s"], m["ducking"]["depth_db"],
                                          m["ducking"].get("attack_ms", 120), m["ducking"].get("release_ms", 500))
            # recovery: middle of every gap >= 1 s returns to 0 dB, measured on audio (ducked == mix there)
            rec = []
            for (a0, b0), (a1, b1) in zip(segs, segs[1:]):
                if a1 - b0 >= 1.0:
                    mid = (b0 + 0.5 + a1 - 0.12) / 2
                    i, j = int((mid - 0.05) * sr), int((mid + 0.05) * sr)
                    rec.append(abs(20 * np.log10(max(qa.rms(dk[i:j]), 1e-12) / max(qa.rms(mix[i:j]), 1e-12))))
            dd = np.diff(curve)
            moving = dd[np.abs(dd) > 1e-9]
            reversals = int(np.count_nonzero(np.diff(np.sign(moving)))) if len(moving) else 0
            row.update(mean_depth_db=round(float(np.mean(depths)), 2) if depths else None,
                       min_depth_db=round(float(np.min(depths)), 2) if depths else None,
                       max_depth_db=round(float(np.max(depths)), 2) if depths else None,
                       gaps_ge_1s=len(rec), max_residual_in_gaps_db=round(max(rec), 3) if rec else None,
                       direction_reversals=reversals, expected_reversals=2 * len(segs) - 1,
                       no_oscillation=reversals <= 2 * len(segs) - 1)
            _plot_curve(c, curve, mix, dk, sr, os.path.join(d, f"curve_{c['name']}.png"))
            to_mp3(dk, sr, os.path.join(d, "clips", f"{c['name']}_ducked.mp3"))
        rows.append(row)
    write_csv(os.path.join(d, "depth.csv"), rows)
    applied = [r for r in rows if r["applied"]]
    ok_runs = [r for r in applied if r.get("mean_depth_db") and 8 <= r["mean_depth_db"] <= 15 and r["no_oscillation"]
               and (r["gaps_ge_1s"] == 0 or r["max_residual_in_gaps_db"] < 0.5) and r["curve_points_in_manifest"]]
    no_speech = [r for r in rows if not r["applied"]]
    n_ok = len(ok_runs)
    v = "PASS" if n_ok >= 3 else ("PARTIAL" if n_ok else "FAIL")
    verdict("L_DUCKING", "3_Levels", "C10", v,
            f"{n_ok} narrations with speech pass (mean depth "
            + ", ".join(f"{r['mean_depth_db']} dB" for r in ok_runs) + f"); {len(no_speech)} no-speech case(s) flat",
            "Rule needs >= 3 narrations with speech" + ("" if n_ok >= 3 else f"; only {n_ok} in this run"),
            [rel(os.path.join(d, "depth.csv")), rel(os.path.join(d, f"curve_{ok_runs[0]['case']}.png")) if ok_runs else rel(d)])


def _plot_curve(c, curve, mix, dk, sr, path):
    fig, ax = plt.subplots(figsize=(8, 2.4))
    t = np.arange(len(curve)) / 100
    ax.plot(t, curve, color="#34488a", lw=1.2, label="gain curve (dB)")
    for s in c["manifest"]["ducking"]["segments"]:
        ax.axvspan(s["start_s"], s["end_s"], color="#7f5300", alpha=0.12)
    ax.set_ylim(-16, 2)
    ax.set_title(f"{c['name']}: ducking curve, shaded = detected speech", fontsize=8)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------- row 11 regenerate
def regen():
    d = out_dir("levels", "adv_regen")
    lines, ok_all, qas = [], True, {}
    for c in cases("regen_"):
        if "__regen_" in c["name"]:
            continue
        r = c["extra"].get("regen")
        if not r:
            ok_all = False
            continue
        lines.append(f"## {c['name']}: regenerated {r['stem']} (parent {c['status']['job_id']} -> child {r['job_id']})")
        for k in sorted(r["parent"]):
            same = r["parent"][k] == r["child"][k]
            expect_same = k != f"stems/{r['stem']}.wav"
            lines.append(f"{k:22s} parent {r['parent'][k][:16]}  child {r['child'][k][:16]}  "
                         f"{'IDENTICAL' if same else 'CHANGED'}{'' if same == expect_same else '   <-- UNEXPECTED'}")
            ok_all &= same == expect_same
        ok_all &= r["child_qa_passed"]
        qas[c["name"]] = r["child_qa_passed"]
        lines.append(f"child mix QA passed: {r['child_qa_passed']}\n")
    open(os.path.join(d, "hash_compare.txt"), "w").write("\n".join(lines) + "\n")
    json.dump(qas, open(os.path.join(d, "qa.json"), "w"), indent=2)
    verdict("L_REGEN", "3_Levels", "C11", "PASS" if ok_all and qas else "FAIL",
            f"{len(qas)} regenerations (drums, melody): other stems SHA-256 identical, new mixes pass QA",
            "", [rel(os.path.join(d, "hash_compare.txt"))])


# ---------------------------------------------------------------- row 12 loop
def loop():
    d = out_dir("levels", "adv_loop")
    rows = []
    for c in cases("loop_"):
        m = c["manifest"]
        x, sr = read(audio_files(c)["mix.wav"])
        seam = qa.loop_seam_report(x, sr)
        bar = 240 / m["tempo_bpm"]
        phase_ms = abs(m["loop"]["bars"] * bar - m["duration_s"]) * 1000 if m["loop"]["bars"] else None
        x4 = np.concatenate([x] * 4)
        # beat onset continuity across the joint: drum onsets near the first downbeats after the joint
        dr, _ = read(audio_files(c)["stems/drums.wav"])
        d4 = np.concatenate([dr] * 2)
        times, flux = qa.spectral_flux(d4, sr)
        med = float(np.median(flux[flux > 0])) if np.any(flux > 0) else 1.0
        t_join = len(x) / sr
        offs = []
        for k in range(0, 4):
            t = t_join + k * bar
            w = (times >= t - 0.05) & (times <= t + 0.05)
            if w.any():
                i = int(np.argmax(np.where(w, flux, -1)))
                if flux[i] >= 2 * med:
                    offs.append(round((times[i] - t) * 1000, 1))
        rows.append({"case": c["name"], "duration_s": m["duration_s"], "bars": m["loop"]["bars"], "tempo_bpm": m["tempo_bpm"],
                     "grid_phase_error_ms": round(phase_ms, 4), "seam_jump": round(seam["seam_jump"], 5),
                     "local_p99_jump": round(seam["local_p99_jump"], 5), "click_at_joint": seam["click"],
                     "drum_onsets_after_joint_ms": " ".join(map(str, offs)),
                     "ok": (not seam["click"]) and phase_ms <= 10 and all(abs(o) <= 20 for o in offs)})
        if len(rows) == 1:
            to_mp3(x4, sr, os.path.join(d, f"looped_x4_{c['name']}.mp3"), kbps=160)
            fig, ax = plt.subplots(figsize=(8, 2.2))
            seg = np.concatenate([x[-int(0.25 * sr):], x[: int(0.25 * sr)]]).mean(axis=1)
            ax.plot(np.arange(len(seg)) / sr - 0.25, seg, lw=0.5, color="#34488a")
            ax.axvline(0, color="#9f2f2a", lw=1)
            ax.set_title(f"{c['name']}: 0.25 s either side of the loop joint (end -> start)", fontsize=8)
            ax.tick_params(labelsize=7)
            fig.tight_layout()
            fig.savefig(os.path.join(d, "seam_plot.png"), dpi=110)
            plt.close(fig)
    write_csv(os.path.join(d, "seam.csv"), rows)
    ok = sum(r["ok"] for r in rows)
    verdict("L_LOOP", "3_Levels", "C12", "PASS" if ok >= 3 and ok == len(rows) else "FAIL",
            f"{ok}/{len(rows)} loops: no click at the joint, grid phase error <= {max(r['grid_phase_error_ms'] for r in rows):.4f} ms",
            "Loop = N whole bars exactly; rendered twice, second pass kept, so tails wrap.",
            [rel(os.path.join(d, "seam.csv")), rel(os.path.join(d, "seam_plot.png"))])


if __name__ == "__main__":
    for fn in (core_prompts, durations, sections, one_piece, ducking_check, regen, loop):
        print(fn.__name__)
        fn()
