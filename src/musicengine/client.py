"""Small HTTP client for the API (batch runner, e2e tests, load test). Not used by the service."""
import hashlib
import json
import os
import time
from urllib.parse import urlparse

import httpx


class ApiClient:
    def __init__(self, base: str, token: str = "", timeout: float = 30.0):
        self.base = base.rstrip("/")
        self.run_id = "v1"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.http = httpx.Client(base_url=self.base, headers=headers, timeout=timeout)
        # presigned links are signed for S3_PUBLIC_ENDPOINT; inside docker fetch them via another host
        rw = os.environ.get("S3_DOWNLOAD_REWRITE", "")
        self.rewrite = tuple(rw.split("=", 1)) if "=" in rw else None

    @staticmethod
    def key_for(name: str, body: dict) -> str:
        return "batch-" + hashlib.sha256((name + json.dumps(body, sort_keys=True)).encode()).hexdigest()[:32]

    def submit(self, body: dict, key: str | None = None, correlation_id: str | None = None) -> httpx.Response:
        h = {}
        if key:
            h["Idempotency-Key"] = key
        if correlation_id:
            h["X-Correlation-Id"] = correlation_id
        return self.http.post("/api/v1/music/jobs", json=body, headers=h)

    def regenerate(self, job_id: str, body: dict, key: str | None = None) -> httpx.Response:
        return self.http.post(f"/api/v1/music/jobs/{job_id}/regenerate", json=body,
                              headers={"Idempotency-Key": key} if key else {})

    def upload(self, path: str) -> str:
        with open(path, "rb") as fh:
            r = self.http.post("/api/v1/uploads", files={"file": (os.path.basename(path), fh, "audio/wav")})
        r.raise_for_status()
        return r.json()["url"]

    def status(self, job_id: str) -> dict:
        r = self.http.get(f"/api/v1/jobs/{job_id}")
        r.raise_for_status()
        return r.json()

    def wait(self, job_id: str, timeout: float = 900, interval: float = 0.5) -> dict:
        t0 = time.time()
        while True:
            s = self.status(job_id)
            if s["status"] in ("succeeded", "failed"):
                return s
            if time.time() - t0 > timeout:
                raise TimeoutError(f"job {job_id} still {s['status']} after {timeout}s")
            time.sleep(interval)

    def download(self, url: str, dest: str) -> str:
        headers = {}
        if self.rewrite and url.startswith(self.rewrite[0]):
            headers["Host"] = urlparse(self.rewrite[0]).netloc
            url = self.rewrite[1] + url[len(self.rewrite[0]):]
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with httpx.stream("GET", url, headers=headers, timeout=120) as r:
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in r.iter_bytes():
                    fh.write(chunk)
        return dest

    def download_result(self, status: dict, out_dir: str) -> dict:
        res = status["result"]
        files = {"mix.wav": res["mix_wav"], "music_manifest.json": res["manifest"],
                 **{f"stems/{k}.wav": v for k, v in res["stems"].items()}}
        if res.get("mix_mp3"):
            files["mix.mp3"] = res["mix_mp3"]
        if res.get("mix_ducked"):
            files["mix_ducked.wav"] = res["mix_ducked"]
        return {name: self.download(url, os.path.join(out_dir, name)) for name, url in files.items()}
