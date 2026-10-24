"""E1: execute evidence/run_matrix.yaml against an API and store everything per case.

    python evidence/tools/run_matrix.py --api http://localhost:8000 [--local-control --worker-log .local/logs/worker.log]

Small files (request, status transcript, manifest, QA, checks, per-job logs, file hashes) go to
evidence/runs/<run_id>/<case>/ and are committed. Audio goes to out/evidence/<run_id>/<case>/ (-> audio-pack.zip).
--local-control lets the runner stop/start worker processes on this machine (cold start, FAULT_INJECT runs,
worker-kill run). Without it those cases are recorded as NOT_RUN.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from musicengine.cli import _local_qa, synth_narration  # noqa: E402
from musicengine.client import ApiClient  # noqa: E402
from musicengine.manifest import jsonable  # noqa: E402


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scrub(obj):
    """Drop presigned query strings (signature + access key id) before anything is committed."""
    return json.loads(re.sub(r'(https?://[^"?]+)\?[^"]*', r"\1", json.dumps(obj)))


def git_sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()


class Runner:
    def __init__(self, a):
        self.a = a
        self.client = ApiClient(a.api, a.token)
        self.run_id = a.run_id
        self.ev = os.path.join(ROOT, "evidence", "runs", self.run_id)
        self.audio = os.path.join(ROOT, "out", "evidence", self.run_id)
        os.makedirs(self.ev, exist_ok=True)
        os.makedirs(self.audio, exist_ok=True)
        self.index: list[dict] = []
        self.special: dict = {}
        self.matrix = yaml.safe_load(open(os.path.join(ROOT, "evidence", "run_matrix.yaml")))
        self.worker: subprocess.Popen | None = None

    # ------------------------------------------------------------ worker control (local only)
    def stop_workers(self):
        if self.worker and self.worker.poll() is None:
            try:
                os.killpg(self.worker.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        subprocess.run(["pkill", "-9", "-f", "musicengine.worker.loop"], capture_output=True)
        # the supervisor's spawned worker/job processes do not die with it outside Docker: kill them explicitly
        venv_py = os.path.join(ROOT, ".venv", "bin", "python")
        subprocess.run(["pkill", "-9", "-f", f"{venv_py} -c from multiprocessing"], capture_output=True)
        time.sleep(1.5)
        left = subprocess.run(["pgrep", "-f", "multiprocessing.spawn"], capture_output=True, text=True).stdout.split()
        if left:
            raise RuntimeError(f"worker processes still alive after stop: {left}")

    def start_worker(self, **env):
        log = open(self.a.worker_log, "a")
        e = {**os.environ, "WORKER_CONCURRENCY": str(self.a.concurrency), **{k: str(v) for k, v in env.items()}}
        self.worker = subprocess.Popen([sys.executable, "-m", "musicengine.worker.loop"], env=e, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True, cwd=ROOT)
        time.sleep(2.5)

    # ------------------------------------------------------------ helpers
    def wait(self, job_id: str, timeout: float = 1800) -> tuple[dict, list]:
        transcript, t0 = [], time.time()
        while True:
            st = self.client.status(job_id)
            if not transcript or (transcript[-1]["status"], transcript[-1]["progress"]) != (st["status"], st["progress"]):
                transcript.append({"t": round(time.time() - t0, 3), "status": st["status"], "progress": st["progress"]})
            if st["status"] in ("succeeded", "failed"):
                return st, transcript
            if time.time() - t0 > timeout:
                raise TimeoutError(job_id)
            time.sleep(0.4)

    def job_logs(self, job_id: str, correlation_id: str) -> list:
        out = []
        for path in filter(None, [self.a.worker_log, self.a.api_log]):
            if not os.path.exists(path):
                continue
            for line in open(path, errors="replace"):
                if job_id in line or (correlation_id and correlation_id in line):
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return out

    def store(self, name: str, request: dict, st: dict, transcript: list, files: dict | None, extra: dict | None = None):
        d = os.path.join(self.ev, name)
        os.makedirs(d, exist_ok=True)
        json.dump(request, open(os.path.join(d, "request.json"), "w"), indent=2, ensure_ascii=False)
        json.dump(scrub(st), open(os.path.join(d, "status.json"), "w"), indent=2, ensure_ascii=False)
        with open(os.path.join(d, "transcript.jsonl"), "w") as fh:
            for t in transcript:
                fh.write(json.dumps(t) + "\n")
        with open(os.path.join(d, "logs.jsonl"), "w") as fh:
            for entry in self.job_logs(st["job_id"], f"evidence-{name}"):
                fh.write(json.dumps(entry) + "\n")
        if files:
            json.dump({k: {"sha256": sha256(p), "bytes": os.path.getsize(p)} for k, p in files.items()},
                      open(os.path.join(d, "files.json"), "w"), indent=2)
            shutil.copy(files["music_manifest.json"], os.path.join(d, "music_manifest.json"))
        if extra:
            json.dump(jsonable(extra), open(os.path.join(d, "extra.json"), "w"), indent=2)

    def run_case(self, name: str, request: dict, meta: dict | None = None, key: str | None = None) -> dict:
        meta = meta or {}
        req = {**{"output": self.matrix["defaults"]["output"]}, **request}
        audio_dir = os.path.join(self.audio, name)
        os.makedirs(audio_dir, exist_ok=True)
        if nar := meta.get("narration"):
            path = synth_narration(os.path.join(audio_dir, "narration.wav"), nar["phrases"], nar["duration_s"])
            req["narration_url"] = self.client.upload(path)
        key = key or ApiClient.key_for(f"{self.run_id}:{name}", request)
        r = self.client.submit(req, key=key, correlation_id=f"evidence-{name}")
        row = {"case": name, "http_status": r.status_code}
        if r.status_code != 202:
            row.update(status="rejected", error=r.json().get("error", {}).get("code"))
            self.index.append(row)
            return row
        st, transcript = self.wait(r.json()["job_id"])
        row.update(job_id=st["job_id"], status=st["status"], warnings=" ".join(w["code"] for w in st["warnings"]))
        created, finished = datetime.fromisoformat(st["created_at"]), datetime.fromisoformat(st["finished_at"])
        row["seconds"] = round((finished - created).total_seconds(), 3)
        if st.get("started_at"):
            row["generation_s"] = round((finished - datetime.fromisoformat(st["started_at"])).total_seconds(), 3)
        files, extra = None, {}
        checks = [("expected_status", st["status"] == meta.get("expect_status", "succeeded"))]
        for code in meta.get("expect_warnings", []):
            checks.append((f"warning:{code}", code in {w["code"] for w in st["warnings"]}))
        if st["status"] == "succeeded":
            files = self.client.download_result(st, audio_dir)
            if meta.get("narration"):  # synthesized + uploaded by the runner (kept for the audio pack)
                files["narration.wav"] = os.path.join(audio_dir, "narration.wav")
            qa = _local_qa({k: v for k, v in files.items() if k != "narration.wav"},
                           json.load(open(files["music_manifest.json"])))
            json.dump(jsonable(qa), open(os.path.join(audio_dir, "qa.json"), "w"), indent=2)
            checks.append(("qa_passed", qa["passed"]))
            extra["qa"] = qa
            if stem := meta.get("regenerate"):
                rr = self.client.regenerate(st["job_id"], {"stem": stem},
                                            key=ApiClient.key_for(f"{self.run_id}:{name}:regen", {"stem": stem}))
                rst, rtrans = self.wait(rr.json()["job_id"])
                rfiles = self.client.download_result(rst, os.path.join(audio_dir, f"regen_{stem}"))
                rqa = _local_qa(rfiles, json.load(open(rfiles["music_manifest.json"])))
                self.store(f"{name}__regen_{stem}", {"parent_job_id": st["job_id"], "stem": stem}, rst, rtrans, rfiles,
                           {"qa": rqa})
                extra["regen"] = {"job_id": rst["job_id"], "stem": stem,
                                  "parent": {k: sha256(v) for k, v in files.items() if k.startswith("stems/")},
                                  "child": {k: sha256(v) for k, v in rfiles.items() if k.startswith("stems/")},
                                  "child_qa_passed": rqa["passed"]}
                same = all(extra["regen"]["parent"][k] == extra["regen"]["child"][k]
                           for k in extra["regen"]["parent"] if k != f"stems/{stem}.wav")
                checks += [("regen_others_identical", same),
                           ("regen_stem_changed", extra["regen"]["parent"][f"stems/{stem}.wav"]
                            != extra["regen"]["child"][f"stems/{stem}.wav"]),
                           ("regen_qa_passed", rqa["passed"])]
        extra["checks"] = [{"name": n, "ok": bool(ok)} for n, ok in checks]
        row["checks_ok"] = all(ok for _, ok in checks)
        row["failed_checks"] = " ".join(n for n, ok in checks if not ok)
        self.store(name, req, st, transcript, files, extra)
        self.index.append(row)
        print(f"{name:34s} {row['status']:9s} {row.get('seconds', '')!s:>8} checks={'ok' if row['checks_ok'] else 'FAIL ' + row['failed_checks']}",
              flush=True)
        return row

    # ------------------------------------------------------------ groups
    def run_standard(self):
        m = self.matrix
        cp = m["core_prompts"]
        for i, (style, prompt) in enumerate(cp["prompts"].items()):
            self.run_case(f"core_{style}", {"prompt": prompt, "duration_s": cp["duration_s"], "seed": cp["seed"] + i})
        du = m["durations"]
        for D in du["values"]:
            self.run_case(f"duration_{D:03d}s", {"prompt": du["prompt"], "duration_s": D, "seed": du["seed"]})
        for name, c in m["cases"].items():
            self.run_case(name, c["request"], c.get("meta"))

    def run_determinism(self):
        c = self.matrix["special"]["determinism"]
        a = self.run_case("determinism_a", c, key=f"{self.run_id}-det-a")
        b = self.run_case("determinism_b", c, key=f"{self.run_id}-det-b")
        fa = json.load(open(os.path.join(self.ev, "determinism_a", "files.json")))
        fb = json.load(open(os.path.join(self.ev, "determinism_b", "files.json")))
        wav = [k for k in fa if k.endswith(".wav")]
        self.special["determinism"] = {"jobs": [a["job_id"], b["job_id"]], "files": wav,
                                       "identical": {k: fa[k]["sha256"] == fb[k]["sha256"] for k in wav}}

    def run_concurrency(self):
        c = self.matrix["special"]["concurrency"]
        prompts = ["lofi beats", "epic trailer", "jazz lounge", "rock anthem", "ambient pad", "corporate"][: c["jobs"]]
        ids, t0 = [None] * c["jobs"], time.time()

        def go(i):
            r = self.client.submit({"prompt": prompts[i], "duration_s": c["duration_s"], "seed": c["seed"] + i},
                                   key=f"{self.run_id}-conc-{i}", correlation_id=f"evidence-concurrency-{i}")
            ids[i] = (r.status_code, r.json().get("job_id"), time.time() - t0)

        ts = [threading.Thread(target=go, args=(i,)) for i in range(c["jobs"])]
        [t.start() for t in ts]
        [t.join() for t in ts]
        results = []
        for i, (code, jid, sent) in enumerate(ids):
            st, tr = self.wait(jid)
            self.store(f"concurrency_{i}", {"prompt": prompts[i], "duration_s": c["duration_s"]}, st, tr, None)
            results.append({"job_id": jid, "http": code, "submitted_at_s": round(sent, 3), "status": st["status"],
                            "started_at": st["started_at"], "finished_at": st["finished_at"]})
        self.special["concurrency"] = {"jobs": results, "distinct_job_ids": len({r["job_id"] for r in results}),
                                       "all_succeeded": all(r["status"] == "succeeded" for r in results)}
        print("concurrency", self.special["concurrency"]["distinct_job_ids"], "distinct,",
              "all succeeded" if self.special["concurrency"]["all_succeeded"] else "NOT all succeeded", flush=True)

    def run_same_key(self):
        c = self.matrix["special"]["same_key"]
        body = {"prompt": c["prompt"], "duration_s": c["duration_s"], "seed": c["seed"]}
        seq_key = f"{self.run_id}-same-seq"
        seq = [self.client.submit(body, key=seq_key).json()["job_id"] for _ in range(2)]
        par_key, par = f"{self.run_id}-same-par", []
        body_p = {**body, "seed": c["seed"] + 1}
        ts = [threading.Thread(target=lambda: par.append(self.client.submit(body_p, key=par_key).json()["job_id"]))
              for _ in range(2)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        conflict = self.client.submit({**body, "duration_s": c["duration_s"] + 1}, key=seq_key)
        out = {"sequential": seq, "parallel": par, "different_body_same_key_http": conflict.status_code,
               "different_body_error": conflict.json().get("error", {}).get("code")}
        for label, jid in (("sequential", seq[0]), ("parallel", par[0])):
            st, tr = self.wait(jid)
            self.store(f"same_key_{label}", body, st, tr, None)
            out[f"{label}_status"] = st["status"]
            logs = self.job_logs(jid, "")
            out[f"{label}_job_started_events"] = sum(1 for e in logs if e.get("event") == "job_started")
        out.update(self.db_and_s3_counts(seq[0], body["prompt"]))
        self.special["same_key"] = out
        print("same_key", out, flush=True)

    def db_and_s3_counts(self, job_id: str, prompt: str) -> dict:
        try:
            from musicengine import db
            from musicengine.storage import Storage

            with db.conn_ctx() as c:
                rows = c.execute("SELECT count(*) AS n FROM jobs WHERE request->>'prompt' = %s AND "
                                 "created_at > now() - interval '1 hour'", (prompt,)).fetchone()["n"]
            keys = Storage().list_keys(f"jobs/{job_id}/")
            return {"db_rows_for_prompt_last_hour": rows, "s3_objects_under_prefix": len(keys)}
        except Exception as e:  # noqa: BLE001 - remote API: no direct DB access
            return {"db_check": f"NOT_RUN ({type(e).__name__})"}

    # ------------------------------------------------------------ local-only
    def run_speed(self):
        c = self.matrix["special"]["speed"]
        body = {"prompt": c["prompt"], "duration_s": c["duration_s"]}
        out = {"cold": None, "warm": []}
        if self.a.local_control:
            self.stop_workers()
            self.start_worker()
            out["cold"] = self.run_case("speed_cold", {**body, "seed": c["seed"]}).get("generation_s")
        for i in range(c["warm_runs"]):
            out["warm"].append(self.run_case(f"speed_warm_{i}", {**body, "seed": c["seed"] + 1 + i}).get("generation_s"))
        self.special["speed"] = out

    def run_faults(self):
        lo = self.matrix["special"]["local_only"]
        if not self.a.local_control:
            self.special["faults"] = "NOT_RUN (needs --local-control)"
            return
        res = {}
        for fault in lo["fault_inject"]:
            self.stop_workers()
            self.start_worker(FAULT_INJECT=fault)
            row = self.run_case(f"fault_{fault}", {"prompt": "Calm piano", "duration_s": 10, "seed": 901},
                                {"expect_warnings": ["PROVIDER_FALLBACK_USED"]}, key=f"{self.run_id}-{fault}")
            res[fault] = row
        self.stop_workers()
        self.start_worker(FAULT_INJECT="render_primary_fail", RENDERER_FALLBACK="")
        res["no_fallback"] = self.run_case("fault_no_fallback", {"prompt": "Calm piano", "duration_s": 10, "seed": 902},
                                           {"expect_status": "failed"})
        self.stop_workers()
        # worker killed mid-job -> stale heartbeat -> re-queued -> completes
        wk = lo["worker_kill"]
        self.start_worker(HEARTBEAT_STALE_S=3)
        r = self.client.submit({"prompt": "Calm ambient that builds", "duration_s": wk["duration_s"], "seed": wk["seed"]},
                               key=f"{self.run_id}-kill", correlation_id="evidence-worker_kill")
        jid = r.json()["job_id"]
        t0 = time.time()
        while self.client.status(jid)["status"] != "running" and time.time() - t0 < 60:
            time.sleep(0.2)
        time.sleep(1.0)
        before = self.client.status(jid)
        self.stop_workers()
        time.sleep(1)
        mid = self.client.status(jid)
        self.start_worker(HEARTBEAT_STALE_S=3)
        st, tr = self.wait(jid)
        self.store("worker_kill", {"duration_s": wk["duration_s"]}, st, tr, None,
                   {"status_before_kill": scrub(before), "status_after_kill": scrub(mid)})
        try:
            from musicengine import db

            with db.conn_ctx() as c:
                attempts = db.get_job(c, jid)["attempts"]
        except Exception:  # noqa: BLE001
            attempts = None
        res["worker_kill"] = {"job_id": jid, "status_when_killed": before["status"], "progress_when_killed": before["progress"],
                              "final_status": st["status"], "attempts": attempts}
        print("worker_kill", res["worker_kill"], flush=True)
        self.stop_workers()
        self.start_worker()
        self.special["faults"] = res

    def run_io(self):
        """Callback signature (Integration 3) and narration by http:// URL (Integration 7). The worker is restarted
        with ALLOW_PRIVATE_URLS=true so it may reach this machine's test servers; the SSRF guard itself is shown by
        the narration_url_blocked case."""
        import http.server
        import socketserver

        from musicengine.worker import callbacks

        if not self.a.local_control:
            self.special["io"] = "NOT_RUN (needs --local-control)"
            return
        secret = "evidence-callback-secret"
        got = []

        class H(http.server.SimpleHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                got.append({"body": body.decode(), "signature": self.headers.get("X-IncuBrix-Signature"),
                            "correlation": self.headers.get("X-Correlation-Id")})
                self.send_response(204)
                self.end_headers()

            def log_message(self, *a):
                pass

        nar_dir = os.path.join(self.audio, "url_input_files")
        os.makedirs(nar_dir, exist_ok=True)
        synth_narration(os.path.join(nar_dir, "narration.wav"), [[1, 4], [6, 9]], 12)
        handler = lambda *a, **k: H(*a, directory=nar_dir, **k)  # noqa: E731
        srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        self.stop_workers()
        self.start_worker(ALLOW_PRIVATE_URLS="true", CALLBACK_SECRET=secret)
        try:
            row = self.run_case("io_narration_http_url", {"prompt": "Calm documentary piano", "duration_s": 12, "seed": 950,
                                                          "narration_url": f"http://127.0.0.1:{port}/narration.wav"})
            row2 = self.run_case("io_callback", {"prompt": "Upbeat corporate", "duration_s": 6, "seed": 951,
                                                 "callback_url": f"http://127.0.0.1:{port}/hook"})
            t0 = time.time()
            while not got and time.time() - t0 < 20:
                time.sleep(0.2)
        finally:
            srv.shutdown()
            self.stop_workers()
            self.start_worker()
        cb = got[0] if got else None
        res = {"narration_http_url": {"job_id": row.get("job_id"), "status": row.get("status"),
                                      "ducked": os.path.exists(os.path.join(self.audio, "io_narration_http_url", "mix_ducked.wav"))},
               "callback": None}
        if cb:
            payload = json.loads(cb["body"])
            res["callback"] = {"job_id": row2.get("job_id"), "received_job_id": payload["job_id"],
                               "status": payload["status"], "signature_header": cb["signature"][:20] + "...",
                               "signature_valid": callbacks.verify(cb["body"].encode(), cb["signature"], secret),
                               "wrong_secret_rejected": not callbacks.verify(cb["body"].encode(), cb["signature"], "x")}
            d = os.path.join(self.ev, "io_callback")
            open(os.path.join(d, "callback_received.json"), "w").write(json.dumps(scrub(payload), indent=2))
        self.special["io"] = res
        print("io", res, flush=True)

    def finish(self):
        cols = ["case", "job_id", "status", "seconds", "generation_s", "http_status", "checks_ok", "failed_checks",
                "warnings", "error"]
        with open(os.path.join(self.ev, "runs_index.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(self.index)
        meta = {"run_id": self.run_id, "git_sha": git_sha(), "api": self.a.api, "local_control": self.a.local_control,
                "started": self.started, "finished": datetime.now(timezone.utc).isoformat(),
                "health": self.client.http.get("/health").json(), "special": self.special}
        json.dump(jsonable(meta), open(os.path.join(self.ev, "run_meta.json"), "w"), indent=2)
        latest = os.path.join(ROOT, "evidence", "runs", "LATEST")
        open(latest, "w").write(self.run_id + "\n")
        ok = sum(bool(r.get("checks_ok")) for r in self.index)
        print(f"\n{ok}/{len(self.index)} cases passed their checks -> {self.ev}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--token", default=os.environ.get("API_TOKEN", ""))
    ap.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--local-control", action="store_true")
    ap.add_argument("--worker-log", default=os.path.join(ROOT, ".local", "logs", "worker.log"))
    ap.add_argument("--api-log", default=os.path.join(ROOT, ".local", "logs", "api.log"))
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--only", default="", help="standard,determinism,concurrency,same_key,speed,faults")
    a = ap.parse_args()
    r = Runner(a)
    r.started = datetime.now(timezone.utc).isoformat()
    groups = (a.only or "standard,determinism,concurrency,same_key,speed,faults,io").split(",")
    if a.local_control:
        r.stop_workers()
        r.start_worker()
    for g in groups:
        getattr(r, {"standard": "run_standard"}.get(g, f"run_{g}"))()
    r.finish()


if __name__ == "__main__":
    main()
