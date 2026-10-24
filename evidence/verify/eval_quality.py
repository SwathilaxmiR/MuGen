"""E4: 3_Levels rows 13-14 and 5_Metrics row 10 from evidence/eval/* (CLAP via clap_eval.py, bleed, approach B,
blind test responses supplied by a human)."""
import csv
import json
import os
import statistics
import subprocess

from common import EV, ROOT, out_dir, rel, run_id, verdict, write_csv  # noqa: E402

D = out_dir("eval")
ASSUMED_USD_PER_HOUR = 0.10


def clap():
    if not os.path.exists(os.path.join(D, "clap.csv")) or os.environ.get("EVIDENCE_RECLAP"):
        p = subprocess.run([os.path.join(ROOT, "eval", ".venv", "bin", "python"), "evidence/verify/clap_eval.py", run_id()],
                           cwd=ROOT, env={**os.environ, "HF_HOME": os.path.join(ROOT, "eval", ".cache")},
                           capture_output=True, text=True)
        open(os.path.join(D, "clap_log.txt"), "w").write(p.stdout + p.stderr[-3000:])
    rows = list(csv.DictReader(open(os.path.join(D, "clap.csv"))))
    m = [float(r["clap_matched"]) for r in rows]
    c = [float(r["clap_mismatched_mean"]) for r in rows]
    top1 = sum(r["rank_of_own_prompt"] == "1" for r in rows)
    return {"n": len(rows), "mean": statistics.mean(m), "sd": statistics.pstdev(m), "control": statistics.mean(c),
            "wins": sum(a > b for a, b in zip(m, c)), "top1": top1}


def bleed():
    src = os.path.join(EV, "metrics", "stem_quality.csv")
    rows = list(csv.DictReader(open(src)))
    write_csv(os.path.join(D, "bleed.csv"), rows)
    return rows


def approaches():
    r = json.load(open(os.path.join(ROOT, "eval", "results", "approach_metrics.json")))
    rows = []
    for side, label in (("A", "A: symbolic + FluidSynth (this engine)"), ("B", "B: MusicGen-small + Demucs")):
        cs = list(r[side].values())
        secs = statistics.mean((x["generate_s"] + x.get("separate_s", 0)) for x in cs)
        D_ = r["B_meta"]["requested_s"]
        per60 = secs * 60 / D_
        rows.append({"approach": label, "n_prompts": len(cs),
                     "clap_mean": round(statistics.mean(x["clap"] for x in cs if x.get("clap") is not None), 3)
                     if side == "B" else None,
                     "seconds_per_60s_music": round(per60, 1),
                     "usd_per_music_minute_at_assumed_machine_price": round(ASSUMED_USD_PER_HOUR * per60 / 3600, 6),
                     "max_length_error_s": max(x["length_error_s"] for x in cs),
                     "stem_sum_diff_db": round(statistics.mean(x["sum_diff_db"] for x in cs), 1),
                     "max_abs_xcorr": round(statistics.mean(x["max_abs_xcorr"] for x in cs), 3),
                     "licence": "owned + MIT SoundFont" if side == "A" else "MusicGen weights CC-BY-NC-4.0 (non-commercial)"})
    # CLAP for A from eval/results/clap_a30.md (same model, same prompts)
    import re

    a_clap = [float(m.group(1)) for line in open(os.path.join(ROOT, "eval", "results", "clap_a30.md"))
              if (m := re.match(r"\| \w+ \| .* \| (-?[\d.]+) \| -?[\d.]+ \| \d+/\d+ \|", line))]
    rows[0]["clap_mean"] = round(statistics.mean(a_clap), 3)
    write_csv(os.path.join(D, "approach_comparison.csv"), rows)
    md = open(os.path.join(ROOT, "eval", "results", "approach_comparison.md")).read()
    open(os.path.join(D, "approach_comparison.md"), "w").write(
        md + f"\n\n**Cost per minute of music** (same machine, CPU, at an assumed ${ASSUMED_USD_PER_HOUR}/h): "
        f"A ${rows[0]['usd_per_music_minute_at_assumed_machine_price']:.6f}, B ${rows[1]['usd_per_music_minute_at_assumed_machine_price']:.6f}. "
        "API fees $0 for both (self-hosted).\n\n**Recommendation:** run A in production: exact length and stems by "
        "construction, ~70x faster, licence-clean; B's open weights are non-commercial. Source: REPORT.md section 6.\n")
    return rows


def main():
    cl = clap()
    bleed()
    ap = approaches()
    blind = os.path.join(D, "blind_test", "responses.csv")
    have_blind = os.path.exists(blind)
    if have_blind:
        resp = list(csv.DictReader(open(blind)))
        listeners = len({r.get("listener") for r in resp})
        ours = sum(r.get("preferred") == "ours" for r in resp)
        nontied = sum(r.get("preferred") in ("ours", "baseline") for r in resp)
        write_csv(os.path.join(D, "blind_test", "summary.csv"),
                  [{"listeners": listeners, "answers": len(resp), "ours": ours, "non_tied": nontied,
                    "ours_pct_of_non_tied": round(100 * ours / max(nontied, 1), 1)}])
    v13 = "PASS" if have_blind and listeners >= 5 else "PENDING_HUMAN"
    verdict("L_MEASURED_QUALITY", "3_Levels", "C13", v13,
            f"CLAP (laion/clap-htsat-unfused) matched {cl['mean']:.3f} vs mismatched {cl['control']:.3f} over {cl['n']} "
            f"prompts; bleed/xcorr per stem in bleed.csv; blind test: {'done' if have_blind else 'NOT RUN'}",
            "Blind A/B test with >= 5 listeners is a human task (eval/listening_test.md); until it is done this stays empty.",
            [rel(os.path.join(D, "clap.csv")), rel(os.path.join(D, "bleed.csv")), "eval/listening_test.md"])
    verdict("L_TWO_APPROACHES", "3_Levels", "C14", "PASS",
            f"A vs B on 5 prompts: CLAP {ap[0]['clap_mean']} vs {ap[1]['clap_mean']}; {ap[0]['seconds_per_60s_music']} vs "
            f"{ap[1]['seconds_per_60s_music']} s per 60 s; ${ap[0]['usd_per_music_minute_at_assumed_machine_price']} vs "
            f"${ap[1]['usd_per_music_minute_at_assumed_machine_price']}/min; recommend A",
            "Small sample (n=5, one seed); B on CPU. Cost uses one assumed machine price for both.",
            [rel(os.path.join(D, "approach_comparison.md")), rel(os.path.join(D, "approach_comparison.csv")), "REPORT.md"])
    if have_blind:
        val = f"CLAP {cl['mean']:.3f} ± {cl['sd']:.3f} (control {cl['control']:.3f}); blind test see summary.csv"
        v = "PASS"
    else:
        val = (f"CLAP {cl['mean']:.3f} ± {cl['sd']:.3f} (mismatched control {cl['control']:.3f}, matched higher in "
               f"{cl['wins']}/{cl['n']}); listening test: not run yet")
        v = "PARTIAL"
    verdict("METRIC_PROMPT_MATCH", "5_Metrics", "C10", v, val,
            f"{cl['n']} core prompts at 45 s, laion/clap-htsat-unfused (Apache-2.0), CPU",
            [rel(os.path.join(D, "clap.csv")), rel(os.path.join(D, "control_clap.csv"))])


if __name__ == "__main__":
    main()
