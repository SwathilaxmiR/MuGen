"""E0 baseline, secret scan, MH6, 3_Levels row 5, 1_Your_Details automatic cells."""
import json
import os
import re
import subprocess

import httpx
import yaml

from common import EV, ROOT, VERDICTS, git_sha, out_dir, rel, verdict  # noqa: E402

INPUTS = os.path.join(EV, "form_inputs.yaml")


def inputs() -> dict:
    return yaml.safe_load(open(INPUTS)) if os.path.exists(INPUTS) else {}


def baseline(fi):
    sha = git_sha()
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    local = httpx.get(os.environ.get("EVIDENCE_API", "http://localhost:8000") + "/health", timeout=5).json()
    demo = None
    if fi.get("demo_url"):
        try:
            demo = httpx.get(fi["demo_url"].rstrip("/") + "/health", timeout=10).json()
        except Exception as e:  # noqa: BLE001
            demo = {"error": str(e)}
    b = {"repo_sha": sha, "clean_tree": not dirty, "dirty_files": dirty.splitlines()[:30], "local_api_health": local,
         "local_api_sha_matches": local.get("git_sha") == sha, "demo_url": fi.get("demo_url"), "demo_health": demo,
         "demo_sha_matches": bool(demo and demo.get("git_sha") == sha),
         "note": "Demo not deployed yet: deploy with deploy/docker-compose.deploy.yml, then set demo_url in "
                 "evidence/form_inputs.yaml and re-run make evidence." if not fi.get("demo_url") else ""}
    json.dump(b, open(os.path.join(EV, "baseline.json"), "w"), indent=2)
    return b


def secret_scan():
    d = out_dir("security")
    p = subprocess.run([os.path.join(ROOT, ".venv", "bin", "detect-secrets"), "scan"], capture_output=True, text=True, cwd=ROOT)
    res = json.loads(p.stdout or "{}").get("results", {})
    findings = [{"file": f, "type": h["type"], "line": h["line_number"]} for f, hs in res.items() for h in hs]
    known = {".env.example": "documented local-dev MinIO defaults (minioadmin) / placeholder CALLBACK_SECRET",
             "src/musicengine/config.py": "same documented local-dev defaults",
             "docker-compose.yml": "compose defaults for the local MinIO",
             "tests/": "test fixtures (fake tokens such as 't0ken', 's3cret')",
             "evidence/tools/run_matrix.py": "test callback secret used only against a local receiver",
             "evidence/must_haves/mh4_licences/texts/": "licence text"}
    for f in findings:
        f["classified"] = next((v for k, v in known.items() if f["file"].startswith(k)), "REVIEW")
    # extra: presigned signatures / access keys / provider keys anywhere in tracked files
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=ROOT).stdout.split()
    pat = re.compile(r"X-Amz-Signature=|X-Amz-Credential=|sk-ant-[A-Za-z0-9]|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH) PRIVATE KEY")
    extra = []
    for f in tracked:
        full = os.path.join(ROOT, f)
        if not os.path.isfile(full) or os.path.getsize(full) > 5_000_000:
            continue
        try:
            for i, line in enumerate(open(full, errors="ignore"), 1):
                if pat.search(line):
                    extra.append(f"{f}:{i}")
        except Exception:  # noqa: BLE001
            pass
    review = [f for f in findings if f["classified"] == "REVIEW"]
    txt = (f"detect-secrets {subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'detect-secrets'), '--version'], capture_output=True, text=True).stdout.strip()} "
           f"scan of git-tracked files at {git_sha()}\n\nfindings: {len(findings)}\n"
           + "\n".join(f"  {f['file']}:{f['line']} {f['type']}  -> {f['classified']}" for f in findings)
           + f"\n\nregex scan (presigned signatures, AWS keys, Anthropic keys, private keys): {extra or 'none'}\n"
           f"needs review: {len(review)}\n(gitleaks/trufflehog not installed here; detect-secrets used instead)\n")
    open(os.path.join(d, "secret_scan.txt"), "w").write(txt)
    return not review and not extra, rel(os.path.join(d, "secret_scan.txt"))


def mh6_and_core(fi, b):
    allv = json.load(open(VERDICTS))
    integ = {k: v["verdict"] for k, v in allv.items() if k.startswith("I") and k[1:].isdigit()}
    all_pass = len(integ) == 10 and all(v == "PASS" for v in integ.values())
    demo_ok = bool(b.get("demo_health") and b["demo_health"].get("status") == "ok")
    if not fi.get("demo_url"):
        v, note = "FAIL", "No public demo is deployed yet, and docker compose has not been run (Integration 1 is Partial)."
    else:
        v = "PASS" if all_pass and demo_ok else "FAIL"
        note = f"demo /health {'ok' if demo_ok else 'not ok'}; integration: {integ}"
    verdict("MH6", "2_Must_haves", "C11", v, f"integration {sum(x == 'PASS' for x in integ.values())}/10 PASS; demo "
            f"{'up' if demo_ok else 'not deployed' if not fi.get('demo_url') else 'down'}",
            note + (" Uptime monitor + 'will stay up until results' must be stated by you." if v == "PASS" else ""),
            ["evidence/baseline.json", "evidence/integration"])
    allv = json.load(open(VERDICTS))
    mh = {k: allv[k]["verdict"] for k in ("MH1", "MH2", "MH3", "MH4", "MH5", "MH6") if k in allv}
    listen = os.path.join(EV, "listening", "log.csv")
    import csv

    logged = os.path.exists(listen) and any(r.get("rating/pass", "").strip() for r in csv.DictReader(open(listen)))
    allok = len(mh) == 6 and all(x == "PASS" for x in mh.values())
    verdict("L_ALL_MUST_HAVES", "3_Levels", "C5", "PASS" if allok and logged else ("PENDING_HUMAN" if allok else "FAIL"),
            f"must-haves: {mh}", "Needs every must-have PASS and the human listening checks logged.", ["evidence/verdicts.json"])


def details(fi, b, secrets_ok, secrets_file):
    hw = json.load(open(os.path.join(EV, "metrics", "hardware.json")))
    costs = json.load(open(os.path.join(EV, "metrics", "costs.json")))
    speed = json.load(open(VERDICTS)).get("METRIC_SPEED", {})
    verdict("D_DEMO_URL", "1_Your_Details", "B9", "PASS" if fi.get("demo_url") and b["demo_sha_matches"] else "HUMAN",
            fi.get("demo_url") or "", "Deploy, then set demo_url in evidence/form_inputs.yaml", ["evidence/baseline.json"])
    verdict("D_TOKEN", "1_Your_Details", "B10", "HUMAN", "", "Token goes in the form only (form_inputs.yaml is git-ignored)", [])
    verdict("D_COLD_START", "1_Your_Details", "B11", "HUMAN" if not fi.get("demo_url") else "PASS",
            "none (always-on); first job after a worker restart: " + speed.get("value", "n/a"),
            "Fill once the demo is deployed and always-on", ["evidence/metrics/speed.csv"])
    verdict("D_REPO", "1_Your_Details", "B12", "PASS" if fi.get("repo_url") else "HUMAN",
            f"{fi.get('repo_url', '')} (all repo paths are relative to tag submission-v1)" if fi.get("repo_url") else "",
            "Set repo_url in form_inputs.yaml (private repo, reviewer invited)", [])
    verdict("D_REPORT", "1_Your_Details", "B14", "PASS" if fi.get("repo_url") else "HUMAN",
            f"{fi.get('repo_url', '').rstrip('/')}/blob/submission-v1/REPORT.md" if fi.get("repo_url") else "REPORT.md",
            "", ["REPORT.md"])
    verdict("D_COMPUTE", "1_Your_Details", "B15", "PASS",
            f"Laptop: {hw['machine']} ({hw['cpu']}, {hw['cores']} cores, {hw['ram_gb']} GB RAM, {hw['os']}); GPU: none",
            "All measured runs on this machine; services run natively (no Docker)", ["evidence/metrics/hardware.json"])
    verdict("D_PAID", "1_Your_Details", "B16", "HUMAN",
            f"Runtime: none, $0 ({costs['paid_services_runtime']}). Development: AI coding assistant subscription (your cost)",
            "Confirm the development-tool cost yourself", ["evidence/metrics/costs.json"])
    verdict("D_AI_TOOLS", "1_Your_Details", "B17", "HUMAN",
            "Claude Code (Anthropic, Claude Opus 5.5) wrote code, tests and docs from my plan; details in AI_USE.md",
            "Confirm wording (AI_USE.md)", ["AI_USE.md"])
    verdict("SECRETS", "7_Declaration", "support", "PASS" if secrets_ok else "FAIL", "secret scan",
            "supports declaration item 'No API keys or secrets...'", [secrets_file])


if __name__ == "__main__":
    fi = inputs()
    b = baseline(fi)
    ok, f = secret_scan()
    mh6_and_core(fi, b)
    details(fi, b, ok, f)
