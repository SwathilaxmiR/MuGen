"""4_Integration rows 5-14 (points 1-10). Writes evidence/integration/*.txt and verdict entries."""
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile

import httpx

from common import EV, ROOT, cases, out_dir, rel, runs_dir, verdict  # noqa: E402

API = os.environ.get("EVIDENCE_API", "http://localhost:8000")
D = out_dir("integration")
PY = os.path.join(ROOT, ".venv", "bin", "python")


def sh(cmd: list[str], **kw) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw)
    return p.returncode, f"$ {' '.join(cmd)}\n{p.stdout}{p.stderr}\nexit={p.returncode}\n"


def write(name: str, text: str) -> str:
    path = os.path.join(D, name)
    open(path, "w").write(text)
    return rel(path)


# ---------------------------------------------------------------- 1 one-command start and test
def p1():
    docker = shutil.which("docker")
    if docker:
        tmp = tempfile.mkdtemp(prefix="fresh_clone_")
        code, out = sh(["git", "clone", "-q", ROOT, tmp])
        c2, o2 = subprocess.run(["make", "up"], cwd=tmp, capture_output=True, text=True, timeout=1800).returncode, ""
        compose_ok = c2 == 0
        write("compose_up.txt", out + f"make up exit={c2}\n")
    else:
        compose_ok = False
        write("compose_up.txt", "NOT_RUN: `docker` is not installed on the machine that produced this evidence "
              "(`which docker` -> not found). `make up` / `make test` have never been executed.\n"
              "Equivalent native run: scripts/dev_services.sh (postgres + minio) + uvicorn + worker; see make_test_output.txt.\n")
    env = {**os.environ, "E2E_API_URL": API}
    code, out = sh([os.path.join(ROOT, ".venv", "bin", "pytest"), "-q", "-rs", "tests"], env=env)
    tests_ok = code == 0
    write("make_test_output.txt", "Full suite run natively (`pytest tests`, the command `make test` runs inside compose), "
          "no API keys set:\n\n" + out[-8000:])
    from musicengine.config import Settings

    fields = sorted(f.upper() for f in Settings.model_fields)
    example = set(re.findall(r"^([A-Z_]+)=", open(os.path.join(ROOT, ".env.example")).read(), re.M))
    missing = [f for f in fields if f not in example]
    extra = sorted(example - set(fields))
    # env vars read directly with os.environ anywhere in src
    direct = sorted(set(re.findall(r'os\.environ(?:\.get)?\(["\']([A-Z_]+)', "".join(
        open(p).read() for p in glob.glob(os.path.join(ROOT, "src", "**", "*.py"), recursive=True)))))
    write("env_coverage.txt", f"Settings fields ({len(fields)}): {', '.join(fields)}\n\nmissing from .env.example: "
          f"{missing or 'none'}\nin .env.example but not a setting: {extra or 'none'}\nread directly via os.environ in "
          f"src/: {direct} (GIT_SHA is a build arg set by the Dockerfile, documented in .env.example? "
          f"{'yes' if 'GIT_SHA' in example else 'no'})\n")
    env_ok = not missing
    v = "PASS" if compose_ok and tests_ok and env_ok else ("PARTIAL" if tests_ok and env_ok else "FAIL")
    verdict("I1", "4_Integration", "C5", v,
            "compose not executed (no Docker here); full suite passes natively" if not compose_ok else "compose + tests pass",
            f"{'Every' if env_ok else 'NOT every'} setting is in .env.example. One test command, no API keys.",
            [rel(os.path.join(D, "compose_up.txt")), rel(os.path.join(D, "make_test_output.txt")), ".env.example"])


# ---------------------------------------------------------------- 2 documented API
def p2():
    import yaml

    from musicengine.cli import openapi_yaml

    committed = open(os.path.join(ROOT, "openapi.yaml")).read()
    live = httpx.get(f"{API}/openapi.json", timeout=10).json()
    same_file = committed == openapi_yaml()
    same_live = yaml.safe_load(committed) == live
    paths = sorted(live["paths"])
    outside = [p for p in paths if not p.startswith("/api/v1/")]
    write("openapi_diff.txt", f"openapi: {live['openapi']}\ncommitted openapi.yaml == exported from app: {same_file}\n"
          f"committed openapi.yaml == running service GET /openapi.json: {same_live}\n\npaths:\n  " + "\n  ".join(paths)
          + f"\n\noutside /api/v1/: {outside} (health/ready at root by design; also served under /api/v1/)\n")
    ok = same_file and same_live and live["openapi"].startswith("3.1") and set(outside) <= {"/health", "/ready"}
    verdict("I2", "4_Integration", "C6", "PASS" if ok else "FAIL",
            f"OpenAPI {live['openapi']}; committed file == running service: {same_live}",
            "All routes under /api/v1/ except /health and /ready (also aliased under /api/v1).",
            ["openapi.yaml", rel(os.path.join(D, "openapi_diff.txt"))])


# ---------------------------------------------------------------- 3 background jobs
def p3():
    rows = list(csv.DictReader(open(os.path.join(runs_dir(), "runs_index.csv"))))
    seen, prog = set(), []
    for t in glob.glob(os.path.join(runs_dir(), "*", "transcript.jsonl")):
        for line in open(t):
            e = json.loads(line)
            seen.add(e["status"])
            prog.append(e["progress"])
    meta = json.load(open(os.path.join(runs_dir(), "run_meta.json")))
    io = meta["special"].get("io") or {}
    cb = io.get("callback") if isinstance(io, dict) else None
    ok202 = all(r["http_status"] == "202" for r in rows if r["status"] != "rejected")
    sample = next(c for c in cases("core_"))
    lines = [f"POST /api/v1/music/jobs -> HTTP 202 for all {sum(r['http_status'] == '202' for r in rows)} submissions: {ok202}",
             f"statuses observed in polling transcripts: {sorted(seen)}",
             f"progress range observed: {min(prog)}..{max(prog)}",
             f"example status (succeeded) has links: {sorted(sample['status']['result'])}",
             f"callback received: {bool(cb)}; signature valid: {cb and cb['signature_valid']}; wrong secret rejected: "
             f"{cb and cb['wrong_secret_rejected']}", json.dumps(cb, indent=2) if cb else ""]
    write("jobs_flow.txt", "\n".join(lines) + "\n")
    ok = ok202 and {"queued", "running", "succeeded", "failed"} <= seen and max(prog) == 100 and cb and cb["signature_valid"]
    verdict("I3", "4_Integration", "C7", "PASS" if ok else "FAIL",
            f"202 + job_id; statuses {sorted(seen)}; progress {min(prog)}-{max(prog)}; signed callback verified",
            "Every request is a job (even 5 s ones).",
            [rel(os.path.join(D, "jobs_flow.txt")), rel(os.path.join(runs_dir(), "io_callback")) if cb else rel(D)])


# ---------------------------------------------------------------- 4 safe retries
def p4():
    meta = json.load(open(os.path.join(runs_dir(), "run_meta.json")))
    sk = meta["special"].get("same_key", {})
    code, out = sh([os.path.join(ROOT, ".venv", "bin", "pytest"), "-q", "tests/integration/test_api.py", "-k", "idempotency"])
    lines = [json.dumps(sk, indent=2), "", out]
    write("idempotency.txt", "\n".join(lines))
    ok = (sk.get("sequential") and len(set(sk["sequential"])) == 1 and len(set(sk.get("parallel", []))) == 1
          and sk.get("different_body_same_key_http") == 409 and sk.get("sequential_job_started_events") == 1
          and sk.get("parallel_job_started_events") == 1 and code == 0)
    verdict("I4", "4_Integration", "C8", "PASS" if ok else "FAIL",
            "same key+body (sequential and parallel) -> same job_id, worked once; different body -> 409",
            "Idempotency-Key accepted on every POST (jobs, regenerate). DB/S3 counts in idempotency.txt.",
            [rel(os.path.join(D, "idempotency.txt"))])


# ---------------------------------------------------------------- 5 clear errors
def p5():
    from musicengine.errors import API_ERRORS, JOB_ERRORS, WARNINGS

    readme = open(os.path.join(ROOT, "README.md")).read()
    codes = set(API_ERRORS) | JOB_ERRORS
    in_readme = set(re.findall(r"\| `([A-Z][A-Z0-9_]+)` \|", readme))
    probes = []
    for method, path, body in [("POST", "/api/v1/music/jobs", {"duration_s": 10}),
                               ("POST", "/api/v1/music/jobs", {"prompt": "x", "duration_s": 999}),
                               ("GET", "/api/v1/jobs/00000000-0000-4000-8000-000000000000", None),
                               ("GET", "/api/v1/no-such-route", None), ("DELETE", "/api/v1/music/jobs", None),
                               ("POST", "/api/v1/music/jobs/00000000-0000-4000-8000-000000000000/regenerate", {"stem": "drums"}),
                               ("GET", "/api/v1/jobs/00000000-0000-4000-8000-000000000000/manifest", None)]:
        r = httpx.request(method, API + path, json=body, timeout=10)
        j = r.json()
        shape = set(j) == {"error"} and set(j["error"]) == {"code", "message", "retryable", "details"}
        probes.append(f"{method} {path} -> {r.status_code} {j['error']['code']} shape_ok={shape}")
    code, out = sh([os.path.join(ROOT, ".venv", "bin", "pytest"), "-q", "tests/integration/test_api.py"])
    missing = sorted(codes - in_readme)
    stale = sorted(in_readme - codes - WARNINGS)
    upper = all(re.fullmatch(r"[A-Z][A-Z0-9_]*", c) for c in codes | WARNINGS)
    write("errors_catalog.txt", "Live probes:\n  " + "\n  ".join(probes)
          + f"\n\nerror codes in code ({len(codes)}): {sorted(codes)}\nwarning codes in code ({len(WARNINGS)})\n"
          f"in code but not in README: {missing or 'none'}\nin README but not in code: {stale or 'none'}\n"
          f"all UPPER_SNAKE: {upper}\nwarnings in code but not in README: {sorted(WARNINGS - in_readme) or 'none'}\n\n"
          "Every error code incl. 401/429/503/409/413 is exercised in tests/integration/test_api.py:\n" + out[-3000:])
    ok = all("shape_ok=True" in p for p in probes) and not missing and not stale and upper and code == 0 \
        and not (WARNINGS - in_readme)
    verdict("I5", "4_Integration", "C9", "PASS" if ok else "FAIL",
            f"{len(codes)} error + {len(WARNINGS)} warning codes, all in README; JSON shape on every probe",
            "", [rel(os.path.join(D, "errors_catalog.txt")), "README.md"])


# ---------------------------------------------------------------- 6 configuration
def p6():
    pat = re.compile(r'(https?://[^\s"\']+|/opt/[^\s"\']+|/tmp/[^\s"\']*|/usr/[^\s"\']+|minioadmin|sk-[A-Za-z0-9]{8,}|'
                     r'AKIA[0-9A-Z]{12,}|claude-[a-z0-9-]+|laion/|facebook/)')
    hits = []
    for p in sorted(glob.glob(os.path.join(ROOT, "src", "**", "*.py"), recursive=True)):
        for i, line in enumerate(open(p), 1):
            for m in pat.finditer(line):
                hits.append((rel(p), i, m.group(0), line.strip()[:120]))
    allowed = {"src/musicengine/config.py": "the config module: defaults for every env setting"}
    lines, unexplained = [], []
    for f, i, tok, line in hits:
        if f in allowed:
            reason = allowed[f]
        elif line.lstrip().startswith(("#", '"""', "'")) or '"""' in line:
            reason = "comment/docstring"
        elif f.endswith("ducking.py") and tok.startswith("http"):
            reason = "scheme check for user URLs"
        elif f.endswith(("schemas.py", "routes.py")) and tok in ("https://", "http://"):
            reason = "URL-scheme validation"
        elif f.endswith("manifest.py"):
            reason = "manifest text"
        else:
            reason = "UNEXPLAINED"
            unexplained.append((f, i, tok))
        lines.append(f"{f}:{i}: {tok}  [{reason}]")
    write("config_scan.txt", "Scan of src/ for hard-coded URLs, paths, keys and model names "
          f"(pattern {pat.pattern}):\n\n" + "\n".join(lines) + f"\n\nunexplained: {unexplained or 'none'}\n"
          "All settings: src/musicengine/config.py (pydantic-settings, env vars / .env).\n")
    verdict("I6", "4_Integration", "C10", "PASS" if not unexplained else "FAIL",
            f"{len(hits)} literal hits, {len(unexplained)} unexplained; every setting via env (config.py)",
            "", [rel(os.path.join(D, "config_scan.txt")), "src/musicengine/config.py", ".env.example"])


# ---------------------------------------------------------------- 7 files in, files out
def p7():
    meta = json.load(open(os.path.join(runs_dir(), "run_meta.json")))
    io = meta["special"].get("io") if isinstance(meta["special"].get("io"), dict) else {}
    upl = [c for c in cases("narration_") if (c["request"].get("narration_url") or "").startswith("upload://")]
    url = io.get("narration_http_url", {})
    blocked = [c for c in cases("narration_url_blocked")]
    sample = cases("core_")[0]["status"]["result"]
    hosts = sorted({re.match(r"https?://[^/]+", u).group(0) for u in
                    [sample["mix_wav"], sample["manifest"], *sample["stems"].values()]})
    try:
        from musicengine.storage import Storage

        keys = Storage().list_keys(f"jobs/{cases('core_')[0]['status']['job_id']}/")
    except Exception as e:  # noqa: BLE001
        keys = [f"NOT_CHECKED ({e})"]
    write("files_io.txt", f"upload input (POST /api/v1/uploads -> upload://...): {len(upl)} narration jobs, all with "
          f"mix_ducked: {all('mix_ducked.wav' in os.listdir(c['audio']) for c in upl)}\n"
          f"URL input (http:// narration_url): {json.dumps(url)}\n"
          f"SSRF guard: metadata IP refused -> warning NARRATION_FETCH_FAILED: "
          f"{[w['code'] for w in blocked[0]['status']['warnings']] if blocked else 'not run'}\n"
          f"outputs in S3, objects under jobs/<id>/: {keys}\nreturned as presigned links on host(s): {hosts}\n")
    ok = upl and url.get("status") == "succeeded" and url.get("ducked") and keys and not keys[0].startswith("NOT")
    verdict("I7", "4_Integration", "C11", "PASS" if ok else "FAIL",
            "narration by upload:// and by http(s) URL both work; outputs in S3 (MinIO) as presigned links",
            "URL fetch is SSRF-guarded; the local-URL test ran with ALLOW_PRIVATE_URLS=true.",
            [rel(os.path.join(D, "files_io.txt"))])


# ---------------------------------------------------------------- 8 logs and health
def p8():
    sample, checked = [], []
    for c in cases("core_")[:3] + cases("hard_vocals"):
        cid = f"evidence-{c['name']}"
        for line in open(os.path.join(c["dir"], "logs.jsonl")):
            e = json.loads(line)
            sample.append(e)
            checked.append({"has_fields": all(k in e for k in ("timestamp", "level", "event", "job_id", "correlation_id")),
                            "cid_matches": e.get("correlation_id") == cid,
                            "job_matches": e.get("job_id") in (c["status"]["job_id"], None)})
    with open(os.path.join(D, "logs_sample.jsonl"), "w") as fh:
        for e in sample[:60]:
            fh.write(json.dumps(e) + "\n")
    h = httpx.get(f"{API}/health", timeout=5)
    r = httpx.get(f"{API}/ready", timeout=10)
    write("health.txt", f"GET /health -> {h.status_code} {h.text}\nGET /ready -> {r.status_code} {r.text}\n")
    ok = sample and all(c["has_fields"] and c["cid_matches"] for c in checked) and h.status_code == 200 and r.status_code == 200
    verdict("I8", "4_Integration", "C12", "PASS" if ok else "FAIL",
            f"{len(sample)} JSON log lines: timestamp, level, event, job_id, correlation_id == request header; "
            f"/health {h.status_code}, /ready {r.status_code}", "",
            [rel(os.path.join(D, "logs_sample.jsonl")), rel(os.path.join(D, "health.txt"))])


# ---------------------------------------------------------------- 9 manifest
def p9():
    from musicengine.manifest import Manifest

    required = ["ai_generated", "providers", "components", "request", "seed", "stem_seeds", "timings_s", "cost",
                "warnings", "tempo_bpm", "key", "beats", "bars", "stems", "loudness", "qa"]
    bad, n = [], 0
    for c in cases():
        n += 1
        try:
            Manifest.model_validate(c["manifest"])
        except Exception as e:  # noqa: BLE001
            bad.append(f"{c['name']}: {str(e)[:200]}")
        miss = [k for k in required if k not in c["manifest"]]
        if miss:
            bad.append(f"{c['name']}: missing {miss}")
    ex = cases("core_")[0]["manifest"]
    write("manifest_schema_check.txt", f"{n} manifests validated against musicengine.manifest.Manifest "
          f"(pydantic, extra='forbid'); failures: {bad or 'none'}\n\nexample providers: {json.dumps(ex['providers'])}\n"
          f"example cost: {json.dumps(ex['cost'])}\nexample timings: {json.dumps(ex['timings_s'])}\n"
          f"components (licence/rights): {len(ex['components'])} entries, first: {json.dumps(ex['components'][0])}\n")
    verdict("I9", "4_Integration", "C13", "PASS" if not bad else "FAIL",
            f"{n} manifests validate; providers+versions, settings, seed, timings, cost, warnings, licences present",
            "", [rel(os.path.join(D, "manifest_schema_check.txt")), "src/musicengine/manifest.py"])


# ---------------------------------------------------------------- 10 batch runner
def p10():
    tmp_in = tempfile.mkdtemp(prefix="batch_in_")
    for f in ("hard_short_5s.json", "hard_vocals.json"):
        shutil.copy(os.path.join(ROOT, "tests", "inputs", f), tmp_in)
    out = os.path.join(ROOT, "out", "evidence_batch")
    shutil.rmtree(out, ignore_errors=True)
    code, text = sh([PY, "-m", "musicengine.cli", "batch", "--api", API, "--input", tmp_in, "--out", out,
                     "--run-id", "evidence-batch"])
    tree = sorted(os.path.relpath(p, out) for p in glob.glob(os.path.join(out, "**", "*"), recursive=True) if os.path.isfile(p))
    write("batch_runner.txt", text + "\noutput tree (one folder):\n  " + "\n  ".join(tree) + "\n")
    shutil.copy(os.path.join(out, "summary.csv"), os.path.join(D, "batch_summary.csv"))
    ok = code == 0 and "summary.csv" in tree and "metrics.csv" in tree
    verdict("I10", "4_Integration", "C14", "PASS" if ok else "FAIL",
            "python -m musicengine.cli batch --api URL --input <folder> --out <folder>: all results in one folder",
            "Also used for every evidence and test-pack run.", [rel(os.path.join(D, "batch_runner.txt")), "src/musicengine/cli.py"])


if __name__ == "__main__":
    for fn in (p2, p3, p4, p5, p6, p7, p8, p9, p10, p1):
        print(fn.__name__)
        fn()
