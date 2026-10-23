"""Command line: init-bucket, export-openapi, qa, batch."""
import argparse
import sys


def cmd_init_bucket(_args) -> int:
    from .storage import get_storage

    get_storage().ensure_bucket()
    print("bucket ready")
    return 0


def openapi_yaml() -> str:
    import yaml

    from .api.main import app

    return yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True, width=120)


def cmd_export_openapi(args) -> int:
    with open(args.path, "w") as fh:
        fh.write(openapi_yaml())
    print(f"wrote {args.path}")
    return 0


# ---------------------------------------------------------------- batch runner
def synth_narration(path: str, phrases: list[list[float]], duration_s: float, sr: int = 16000, seed: int = 0) -> str:
    """Speech-like test narration: noise 'syllables' inside phrases, faint room noise elsewhere."""
    import numpy as np
    import soundfile as sf

    rng = np.random.default_rng(seed)
    x = rng.standard_normal(int(duration_s * sr)) * 0.0005
    for a, b in phrases:
        t = a
        while t < b:
            i, j = int(t * sr), int(min(b, t + 0.18) * sr)
            x[i:j] += rng.standard_normal(j - i) * 0.1 * np.hanning(j - i)
            t += 0.25
    sf.write(path, x, sr)
    return path


def _ts(v):
    from datetime import datetime

    return datetime.fromisoformat(v) if v else None


def _local_qa(files: dict, manifest: dict) -> dict:
    from . import mixdown, qa

    sr = manifest["sample_rate"]
    mix, _ = mixdown.read_wav(files["mix.wav"])
    stems = {k[6:-4]: mixdown.read_wav(v)[0] for k, v in files.items() if k.startswith("stems/")}
    extra = {"mix_ducked": mixdown.read_wav(files["mix_ducked.wav"])[0]} if "mix_ducked.wav" in files else None
    mp3_tp = mixdown.mp3_true_peak(files["mix.mp3"], sr, len(mix)) if "mix.mp3" in files else None
    report = qa.run_gate(mix, stems, sr, expected_len=manifest["length_samples"],
                         target_lufs=manifest["loudness"]["target_lufs"], lufs_tol=1.0 if manifest.get(
                             "regenerated_stem") else 0.5, tp_max=-1.0, sections=manifest["sections"],
                         hit_time_s=manifest["hit_time_s"] or manifest["duration_s"], loop=manifest["loop"]["enabled"],
                         mix_path=files["mix.wav"], mp3_tp=mp3_tp, extra_files=extra)
    report["bleed"] = qa.stem_bleed(stems, sr)
    report["spectral_overlap"] = qa.spectral_overlap(stems, sr)
    return report


def _run_case(client, name: str, data: dict, out_root: str, submitted: dict | None = None) -> dict:
    import hashlib
    import json
    import os

    from .client import ApiClient
    from .manifest import jsonable

    meta = data.get("meta", {})
    body = dict(data.get("request", data))
    out = os.path.join(out_root, name)
    os.makedirs(out, exist_ok=True)
    row = {"case": name, "duration_s": body.get("duration_s"), "prompt": body.get("prompt", "")[:80]}
    checks = []
    if submitted is None:
        submitted = _submit_case(client, name, data, out)
    r = submitted["response"]
    row["http_status"] = r.status_code
    if r.status_code != 202:
        row.update(status="rejected", error=r.json().get("error", {}).get("code"))
        checks.append(("expected_http", meta.get("expect_http", 202) == r.status_code))
        _finish(row, checks, out, {"response": r.json()})
        return row
    job_id = r.json()["job_id"]
    if meta.get("submit_twice"):
        again = client.submit(submitted["body"], key=submitted["key"])
        checks.append(("same_job_on_resubmit", again.json().get("job_id") == job_id))
    st = client.wait(job_id, timeout=meta.get("timeout_s", 1200))
    row.update(job_id=job_id, status=st["status"], warnings=" ".join(sorted({w["code"] for w in st["warnings"]})))
    created, started, finished = _ts(st["created_at"]), _ts(st["started_at"]), _ts(st["finished_at"])
    if started and finished:
        row["generation_s"] = round((finished - started).total_seconds(), 3)
        row["queue_s"] = round((started - created).total_seconds(), 3)
    with open(os.path.join(out, "status.json"), "w") as fh:
        json.dump(st, fh, indent=2)
    checks.append(("expected_status", st["status"] == meta.get("expect_status", "succeeded")))
    for code in meta.get("expect_warnings", []):
        checks.append((f"warning:{code}", code in {w["code"] for w in st["warnings"]}))
    if st["status"] != "succeeded":
        row["error"] = (st.get("error") or {}).get("code")
        _finish(row, checks, out, {})
        return row
    files = client.download_result(st, out)
    manifest = json.load(open(files["music_manifest.json"]))
    rep = _local_qa(files, manifest)
    with open(os.path.join(out, "qa.json"), "w") as fh:
        json.dump(jsonable(rep), fh, indent=2)
    m = rep["metrics"]
    D = manifest["duration_s"]
    row.update(style=manifest["style"], tempo_bpm=manifest["tempo_bpm"], key=manifest["key"]["name"],
               qa_passed=rep["passed"], qa_failures=" ".join(rep["failures"]),
               length_error_s=m["length_error_s"], lufs=m["integrated_lufs"],
               ffmpeg_lufs=m["ffmpeg"].get("integrated_lufs"), true_peak_dbtp=m["true_peak_dbtp"],
               ffmpeg_true_peak_dbtp=m["ffmpeg"].get("true_peak_dbtp"), mp3_true_peak_dbtp=m["mp3_true_peak_dbtp"],
               sum_diff_db=m["sum_diff_db"], clicks=m["clicks"], gaps=m["gaps"],
               bleed_max_explained_db=rep["bleed"]["max_explained_db"],
               bleed_per_stem=" ".join(f"{k}:{v['explained_db']}" for k, v in rep["bleed"]["per_stem"].items()),
               max_abs_xcorr=max((abs(v) for v in rep["bleed"]["pairwise_xcorr"].values()), default=0),
               spectral_overlap=rep["spectral_overlap"]["mean_overlap"],
               compute_s=manifest["cost"]["compute_seconds"], cost_usd=manifest["cost"]["usd_estimate"],
               cost_usd_per_min=round(manifest["cost"]["usd_estimate"] / (D / 60), 6),
               worker_total_s=manifest["timings_s"]["total"],
               realtime_factor=round(D / max(manifest["timings_s"]["total"], 1e-6), 2),
               renderer=" ".join(sorted({s["renderer"] for s in manifest["stems"]})),
               ducking_applied=manifest["ducking"].get("applied"))
    if row.get("generation_s"):
        row["seconds_per_60s"] = round(row["generation_s"] * 60 / D, 3)
    checks.append(("qa_passed", rep["passed"]))
    if regen := meta.get("regenerate"):
        rr = client.regenerate(job_id, {"stem": regen}, key=ApiClient.key_for(f"{client.run_id}:{name}:regen", {"stem": regen}))
        rs = client.wait(rr.json()["job_id"])
        rfiles = client.download_result(rs, os.path.join(out, f"regen_{regen}"))
        same = all(hashlib.sha256(open(files[k], "rb").read()).digest() ==
                   hashlib.sha256(open(rfiles[k], "rb").read()).digest()
                   for k in files if k.startswith("stems/") and k != f"stems/{regen}.wav")
        changed = open(files[f"stems/{regen}.wav"], "rb").read() != open(rfiles[f"stems/{regen}.wav"], "rb").read()
        rrep = _local_qa(rfiles, json.load(open(rfiles["music_manifest.json"])))
        checks += [("regen_others_byte_identical", same), ("regen_stem_changed", changed),
                   ("regen_qa_passed", rrep["passed"])]
        row["regen_job_id"] = rs["job_id"]
    _finish(row, checks, out, {})
    return row


def _submit_case(client, name: str, data: dict, out: str) -> dict:
    import json
    import os

    from .client import ApiClient

    meta = data.get("meta", {})
    body = dict(data.get("request", data))
    if nar := meta.get("narration"):
        path = synth_narration(os.path.join(out, "narration.wav"), nar.get("phrases", []), nar["duration_s"])
        body["narration_url"] = client.upload(path)
    with open(os.path.join(out, "request.json"), "w") as fh:
        json.dump(body, fh, indent=2)
    key = ApiClient.key_for(f"{client.run_id}:{name}", {k: v for k, v in body.items() if k != "narration_url"})
    return {"response": client.submit(body, key=key, correlation_id=f"batch-{name}"), "body": body, "key": key}


def _finish(row: dict, checks: list, out: str, extra: dict) -> None:
    import json
    import os

    row["checks_passed"] = all(ok for _, ok in checks)
    row["failed_checks"] = " ".join(n for n, ok in checks if not ok)
    with open(os.path.join(out, "checks.json"), "w") as fh:
        json.dump({"checks": [{"name": n, "ok": ok} for n, ok in checks], **extra}, fh, indent=2)


def cmd_batch(args) -> int:
    import csv
    import glob
    import json
    import os
    from collections import defaultdict

    from .client import ApiClient

    client = ApiClient(args.api, args.token)
    client.run_id = args.run_id
    paths = sorted(glob.glob(os.path.join(args.input, "*.json")))
    if args.only:
        paths = [p for p in paths if any(o in os.path.basename(p) for o in args.only.split(","))]
    os.makedirs(args.out, exist_ok=True)
    cases = [(os.path.basename(p)[:-5], json.load(open(p))) for p in paths]
    groups = defaultdict(list)
    for name, data in cases:
        groups[data.get("meta", {}).get("concurrent_group") or name].append((name, data))
    rows = []
    for _, members in groups.items():
        # members of a concurrent group are all submitted before any is awaited
        subs = {}
        for name, data in members:
            d = os.path.join(args.out, name)
            os.makedirs(d, exist_ok=True)
            subs[name] = _submit_case(client, name, data, d)
        for name, data in members:
            try:
                row = _run_case(client, name, data, args.out, subs[name])
            except Exception as e:  # noqa: BLE001 - keep going, record the failure
                row = {"case": name, "status": "runner_error", "error": f"{type(e).__name__}: {e}",
                       "checks_passed": False}
            rows.append(row)
            print(f"{name:32s} {row.get('status', '?'):10s} checks={'ok' if row.get('checks_passed') else 'FAIL'} "
                  f"{row.get('failed_checks', '') or ''} {row.get('error', '') or ''}", flush=True)
    summary_cols = ["case", "status", "checks_passed", "failed_checks", "http_status", "error", "warnings", "job_id",
                    "style", "duration_s", "prompt"]
    metric_cols = ["case", "duration_s", "style", "renderer", "generation_s", "seconds_per_60s", "queue_s",
                   "worker_total_s", "realtime_factor", "length_error_s", "lufs", "ffmpeg_lufs", "true_peak_dbtp",
                   "ffmpeg_true_peak_dbtp", "mp3_true_peak_dbtp", "sum_diff_db", "bleed_max_explained_db",
                   "bleed_per_stem", "max_abs_xcorr", "spectral_overlap", "clicks", "gaps", "qa_passed",
                   "qa_failures", "compute_s", "cost_usd", "cost_usd_per_min", "ducking_applied", "warnings"]
    for fname, cols in (("summary.csv", summary_cols), ("metrics.csv", metric_cols)):
        with open(os.path.join(args.out, fname), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                if fname == "summary.csv" or r.get("status") == "succeeded":
                    w.writerow(r)
    ok = sum(bool(r.get("checks_passed")) for r in rows)
    print(f"\n{ok}/{len(rows)} cases passed all checks -> {args.out}/summary.csv, {args.out}/metrics.csv")
    return 0 if ok == len(rows) else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="musicengine")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-bucket").set_defaults(fn=cmd_init_bucket)
    e = sub.add_parser("export-openapi")
    e.add_argument("path", nargs="?", default="openapi.yaml")
    e.set_defaults(fn=cmd_export_openapi)
    b = sub.add_parser("batch", help="run every tests/inputs/*.json through the API and measure the results")
    b.add_argument("--api", required=True)
    b.add_argument("--token", default="")
    b.add_argument("--input", default="tests/inputs")
    b.add_argument("--out", default="out")
    b.add_argument("--only", default="", help="comma-separated substrings of case names")
    b.add_argument("--run-id", default="v1", help="part of every Idempotency-Key: same run id = same jobs")
    b.set_defaults(fn=cmd_batch)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
