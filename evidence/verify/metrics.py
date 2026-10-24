"""E3: speed.csv, costs.json, load.csv, hardware.json (+ 5_Metrics rows 5-6, 3_Levels row 15).

    python evidence/verify/metrics.py [--load]     # --load re-runs the load test (restarts local workers)
"""
import argparse
import csv
import json
import os
import platform
import statistics
import subprocess
import time

from common import EV, ROOT, cases, out_dir, rel, runs_dir, verdict, write_csv  # noqa: E402

D = out_dir("metrics")
PY = os.path.join(ROOT, ".venv", "bin", "python")
ASSUMED_USD_PER_HOUR = 0.10  # machine price used for $/min from throughput; replace with the real server price


def hardware() -> dict:
    def sysctl(k):
        return subprocess.run(["sysctl", "-n", k], capture_output=True, text=True).stdout.strip()

    hw = {"cpu": sysctl("machdep.cpu.brand_string") or platform.processor(), "cores": os.cpu_count(),
          "ram_gb": round(int(sysctl("hw.memsize") or 0) / 2**30, 1), "os": platform.platform(),
          "machine": subprocess.run(["sysctl", "-n", "hw.model"], capture_output=True, text=True).stdout.strip(),
          "gpu": "none used (CPU only)", "docker": "not installed (services run natively)",
          "python": platform.python_version(),
          "fluidsynth": subprocess.run(["fluidsynth", "--version"], capture_output=True, text=True).stdout.splitlines()[0],
          "ffmpeg": subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]}
    json.dump(hw, open(os.path.join(D, "hardware.json"), "w"), indent=2)
    return hw


def speed(hw):
    rows = list(csv.DictReader(open(os.path.join(runs_dir(), "runs_index.csv"))))
    sp = [r for r in rows if r["case"].startswith("speed_")]
    out = [{"run": r["case"], "kind": "cold" if r["case"] == "speed_cold" else "warm", "music_s": 60,
            "generation_s": float(r["generation_s"]), "end_to_end_s": float(r["seconds"]), "job_id": r["job_id"]}
           for r in sp if r["generation_s"]]
    write_csv(os.path.join(D, "speed.csv"), out)
    cold = next((r["generation_s"] for r in out if r["kind"] == "cold"), None)
    warm = [r["generation_s"] for r in out if r["kind"] == "warm"]
    med = statistics.median(warm) if warm else None
    hw_s = f"{hw['machine']} ({hw['cpu']}, {hw['cores']} cores, {hw['ram_gb']} GB RAM), CPU only, FluidSynth renderer"
    if cold is None or not warm:
        verdict("METRIC_SPEED", "5_Metrics", "C5", "NOT_RUN", "Not measured", "speed runs missing", [])
        return None, None
    verdict("METRIC_SPEED", "5_Metrics", "C5", "PASS",
            f"cold {cold:.1f} s / warm {med:.1f} s per 60 s of music (median of {len(warm)} warm runs)",
            f"{hw_s}; cold = first job after a worker restart; WORKER_CONCURRENCY=2; no cold start beyond process "
            "spawn because no model is loaded", [rel(os.path.join(D, "speed.csv")), rel(os.path.join(D, "hardware.json"))])
    return cold, med


def costs(hw, warm):
    from musicengine.config import get_settings

    price = get_settings().cost_per_cpu_second
    sixty = [c for c in cases("speed_warm")]
    cpu = [c["manifest"]["cost"]["compute_seconds"] for c in sixty]
    usd = [c["manifest"]["cost"]["usd_estimate"] for c in sixty]
    load = os.path.join(D, "load.csv")
    thr = None
    if os.path.exists(load):
        rows = list(csv.DictReader(open(load)))
        best = max(rows, key=lambda r: float(r["music_minutes_per_hour"]))
        thr = {"concurrency": best["concurrency"], "music_minutes_per_hour": float(best["music_minutes_per_hour"]),
               "usd_per_music_minute_at_assumed_price": round(ASSUMED_USD_PER_HOUR / float(best["music_minutes_per_hour"]), 6)}
    c = {"formula_per_job": "cost = compute_seconds (CPU user+sys of the job process and its fluidsynth/ffmpeg children) "
                            "x COST_PER_CPU_SECOND", "cost_per_cpu_second_usd": price,
         "cost_per_cpu_second_note": "COST_PER_CPU_SECOND default (= $0.048 per vCPU-hour); an assumption, set it to "
                                     "your server's price",
         "measured_compute_seconds_per_60s": round(statistics.median(cpu), 3) if cpu else None,
         "usd_per_minute_of_music": round(statistics.median(usd), 6) if usd else None,
         "formula_server": "usd_per_music_minute = server_usd_per_hour / music_minutes_per_hour (load test)",
         "assumed_server_usd_per_hour": ASSUMED_USD_PER_HOUR, "throughput": thr,
         "api_fees_usd": 0.0, "paid_services_runtime": "none (no paid API, cloud or GPU used to produce or measure outputs)",
         "hardware": hw["machine"]}
    json.dump(c, open(os.path.join(D, "costs.json"), "w"), indent=2)
    if not usd:
        verdict("METRIC_COST", "5_Metrics", "C6", "NOT_RUN", "Not measured", "", [])
        return c
    verdict("METRIC_COST", "5_Metrics", "C6", "PASS",
            f"${c['usd_per_minute_of_music']:.6f} per minute of music (compute only; API fees $0)",
            f"median {c['measured_compute_seconds_per_60s']} CPU-s per 60 s job x ${price}/CPU-s (assumed $0.048 per "
            f"vCPU-hour); by throughput: ${thr['usd_per_music_minute_at_assumed_price'] if thr else 'n/a'}/min at an "
            f"assumed ${ASSUMED_USD_PER_HOUR}/h machine", [rel(os.path.join(D, "costs.json"))])
    return c


def run_load():
    """Restart local workers at concurrency 1/2/4 and run eval/loadtest.py (8 x 60 s jobs each)."""
    rows = []
    for conc in (1, 2, 4):
        subprocess.run(["pkill", "-9", "-f", "musicengine.worker.loop"])
        subprocess.run(["pkill", "-9", "-f", f"{PY} -c from multiprocessing"])
        time.sleep(1.5)
        log = open(os.path.join(ROOT, ".local", "logs", f"worker_load_c{conc}.log"), "w")
        subprocess.Popen([PY, "-m", "musicengine.worker.loop"], env={**os.environ, "WORKER_CONCURRENCY": str(conc)},
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True, cwd=ROOT)
        time.sleep(3)
        p = subprocess.run([PY, "eval/loadtest.py", "--api", "http://localhost:8000", "--jobs", "8", "--duration", "60",
                            "--label", f"concurrency={conc}", "--usd-per-hour", str(ASSUMED_USD_PER_HOUR)],
                           capture_output=True, text=True, cwd=ROOT)
        r = json.loads(p.stdout.strip().splitlines()[-1])
        rows.append({"concurrency": conc, **r})
        print(conc, r, flush=True)
    subprocess.run(["pkill", "-9", "-f", "musicengine.worker.loop"])
    subprocess.run(["pkill", "-9", "-f", f"{PY} -c from multiprocessing"])
    time.sleep(1.5)
    subprocess.Popen([PY, "-m", "musicengine.worker.loop"], env={**os.environ, "WORKER_CONCURRENCY": "2"},
                     stdout=open(os.path.join(ROOT, ".local", "logs", "worker.log"), "a"), stderr=subprocess.STDOUT,
                     start_new_session=True, cwd=ROOT)
    write_csv(os.path.join(D, "load.csv"), rows)


def load_verdict(hw, cold, warm, c):
    path = os.path.join(D, "load.csv")
    if not os.path.exists(path):
        verdict("L_PRODUCTION", "3_Levels", "C15", "NOT_RUN", "load test not run", "", [])
        return
    rows = list(csv.DictReader(open(path)))
    best = max(rows, key=lambda r: float(r["music_minutes_per_hour"]))
    ok = cold is not None and warm is not None and c.get("usd_per_minute_of_music")
    verdict("L_PRODUCTION", "3_Levels", "C15", "PASS" if ok else "FAIL",
            f"60 s of music in {warm:.1f} s warm / {cold:.1f} s cold; ${c['usd_per_minute_of_music']:.6f}/min compute; "
            f"best {float(best['music_minutes_per_hour']):.0f} music-min/h at WORKER_CONCURRENCY={best['concurrency']}",
            f"load test 8 x 60 s at concurrency 1/2/4 on {hw['machine']}: p50 latency "
            + ", ".join(f"c{r['concurrency']} {r['latency_p50_s']} s" for r in rows)
            + "; peak RSS per job " + ", ".join(f"{r.get('peak_job_process_mb')} MB" for r in rows),
            [rel(os.path.join(D, "speed.csv")), rel(path), rel(os.path.join(D, "costs.json"))])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", action="store_true")
    a = ap.parse_args()
    hw = hardware()
    if a.load:
        run_load()
    cold, warm = speed(hw)
    c = costs(hw, warm)
    load_verdict(hw, cold, warm, c)
