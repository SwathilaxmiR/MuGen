"""Load test: submit K concurrent jobs of D seconds and measure latency, throughput and worker RAM.

    python eval/loadtest.py --api http://localhost:8000 --jobs 8 --duration 60 --label conc2 \
        --usd-per-hour 0.145 >> eval/results/loadtest.jsonl

The worker concurrency is whatever the running worker was started with (WORKER_CONCURRENCY); restart the
worker between runs. RAM is sampled with `ps` on the same host (local runs only; pass --no-ram otherwise).
Cost per minute of music = server $/hour / (minutes of music produced per hour at this throughput).
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from musicengine.client import ApiClient  # noqa: E402

PROMPTS = ["upbeat corporate background", "chill lo-fi beats", "epic cinematic score", "smooth jazz lounge",
           "energetic EDM track", "warm acoustic folk", "tense thriller underscore", "calm ambient pad"]


def sample_ram(stop: threading.Event, out: dict):
    """Peak RSS (MB): whole worker tree, and the largest single job process (+ its fluidsynth child)."""
    while not stop.is_set():
        try:
            ps = subprocess.run(["ps", "-axo", "pid=,ppid=,rss=,command="], capture_output=True, text=True).stdout
        except Exception:
            return
        procs = []
        for line in ps.splitlines():
            parts = line.split(None, 3)
            if len(parts) == 4:
                procs.append((int(parts[0]), int(parts[1]), int(parts[2]) / 1024, parts[3]))
        worker = [p for p in procs if "musicengine.worker.loop" in p[3] or "multiprocessing.spawn" in p[3]
                  or ("fluidsynth" in p[3] and "-F" in p[3])]
        total = sum(p[2] for p in worker)
        job = max((p[2] + sum(c[2] for c in procs if c[1] == p[0] and "fluidsynth" in c[3])
                   for p in procs if "multiprocessing.spawn" in p[3]), default=0)
        out["peak_worker_tree_mb"] = max(out.get("peak_worker_tree_mb", 0), total)
        out["peak_job_process_mb"] = max(out.get("peak_job_process_mb", 0), job)
        time.sleep(0.25)


def pct(xs, q):
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--token", default="")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--label", default="")
    ap.add_argument("--usd-per-hour", type=float, required=True, help="server price (state the source)")
    ap.add_argument("--no-ram", action="store_true")
    a = ap.parse_args()
    c = ApiClient(a.api, a.token)
    ram: dict = {}
    stop = threading.Event()
    if not a.no_ram:
        threading.Thread(target=sample_ram, args=(stop, ram), daemon=True).start()
    t0 = time.time()
    ids = []
    for i in range(a.jobs):
        r = c.submit({"prompt": PROMPTS[i % len(PROMPTS)], "duration_s": a.duration, "seed": 1000 + i})
        r.raise_for_status()
        ids.append(r.json()["job_id"])
    sts = [c.wait(j, timeout=3600) for j in ids]
    wall = time.time() - t0
    stop.set()
    ok = [s for s in sts if s["status"] == "succeeded"]

    def secs(s, a_, b_):
        return (datetime.fromisoformat(s[b_]) - datetime.fromisoformat(s[a_])).total_seconds()

    lat = [secs(s, "created_at", "finished_at") for s in ok]
    gen = [secs(s, "started_at", "finished_at") for s in ok]
    music_min_per_hour = len(ok) * a.duration / 60 / wall * 3600
    res = {
        "label": a.label, "jobs": a.jobs, "succeeded": len(ok), "duration_s": a.duration, "wall_s": round(wall, 2),
        "latency_p50_s": round(pct(lat, 0.5), 2), "latency_p95_s": round(pct(lat, 0.95), 2),
        "generation_p50_s": round(pct(gen, 0.5), 2), "generation_mean_s": round(statistics.mean(gen), 2),
        "jobs_per_hour": round(len(ok) / wall * 3600, 1), "music_minutes_per_hour": round(music_min_per_hour, 1),
        "usd_per_hour": a.usd_per_hour, "usd_per_music_minute": round(a.usd_per_hour / music_min_per_hour, 6),
        **{k: round(v, 1) for k, v in ram.items()},
    }
    print(json.dumps(res))


if __name__ == "__main__":
    main()
