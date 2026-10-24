"""E7 consistency: numbers quoted in REPORT.md / README.md must equal the files they cite; every repo path quoted in
the docs must exist. Also writes evidence/declaration_support.md. Output: evidence/consistency.txt."""
import csv
import glob
import json
import os
import re

from common import EV, ROOT, git_sha, rel, verdict  # noqa: E402

REPORT = open(os.path.join(ROOT, "REPORT.md")).read()
README = open(os.path.join(ROOT, "README.md")).read()


def num(s: str) -> float:
    return float(s.replace("−", "-").replace(",", ""))


def find(doc: str, pattern: str) -> list[float]:
    return [num(m) for m in re.findall(pattern, doc)]


def run3():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "testpack", "run3", "metrics.csv"))))
    f = lambda k: [float(r[k]) for r in rows if r[k] not in ("", "None")]  # noqa: E731
    lufs_dev = []
    for r in rows:
        m = json.load(open(os.path.join(ROOT, "testpack", "run3", "cases", r["case"], "music_manifest.json")))
        lufs_dev.append(abs(m["loudness"]["integrated_lufs"] - m["loudness"]["target_lufs"]))
    return {"sum_worst": max(f("sum_diff_db")), "sum_best": min(f("sum_diff_db")), "tp_worst": max(f("true_peak_dbtp")),
            "mp3_worst": max(f("mp3_true_peak_dbtp")), "lufs_dev": max(lufs_dev),
            "ff_delta": max(abs(float(r["lufs"]) - float(r["ffmpeg_lufs"])) for r in rows), "n": len(rows)}


def loadtest():
    rows = [json.loads(line) for line in open(os.path.join(ROOT, "eval", "results", "loadtest.jsonl"))]
    by = {r["label"].split()[0]: r for r in rows}
    return {"c1": by["concurrency=1"]["music_minutes_per_hour"], "c2": by["concurrency=2"]["music_minutes_per_hour"],
            "c4": by["concurrency=4"]["music_minutes_per_hour"], "cold": by["cold:"]["generation_p50_s"],
            "warm": by["warm:"]["generation_p50_s"], "ram300": by["300s"]["peak_job_process_mb"]}


def checks():
    out = []

    def check(label, doc_vals, truth, tol):
        ok = bool(doc_vals) and all(abs(v - truth) <= tol for v in doc_vals)
        out.append({"claim": label, "doc": doc_vals, "source": round(truth, 4), "ok": ok})

    r3 = run3()
    check("REPORT §3 sum-diff worst (run3)", find(REPORT, r"\*\*(−1\d\d\.\d) to"), r3["sum_worst"], 0.05)
    check("REPORT §3 sum-diff best (run3)", find(REPORT, r"to −(1\d\d\.\d) dB\*\*"), -r3["sum_best"], 0.05)
    check("REPORT §3 LUFS within (run3)", find(REPORT, r"Within \*\*(\d\.\d+) LU\*\*"), r3["lufs_dev"], 0.005)
    check("REPORT §3 ffmpeg agrees within (run3)", find(REPORT, r"agrees within \*\*(\d\.\d+) LU\*\*"), r3["ff_delta"], 0.02)
    check("REPORT §3 TP worst (run3)", find(REPORT, r"Worst \*\*(−\d\.\d+) dBTP\*\* WAV"), r3["tp_worst"], 0.005)
    check("REPORT §3 mp3 TP worst (run3)", find(REPORT, r"worst \*\*(−\d\.\d+) dBTP\*\* decoded mp3"), r3["mp3_worst"], 0.005)
    lt = loadtest()
    for c in ("1", "2", "4"):
        check(f"REPORT §7 music-min/h c{c}", find(REPORT, rf"\| {c} \| [\d.]+ \| [\d.]+ / [\d.]+ \| ([\d,]+) \|"), lt[f"c{c}"], 1)
    check("REPORT §7 cold s/60s", find(REPORT, r"cold \(first job after the worker starts\) \*\*(\d\.\d+) s\*\*"), lt["cold"], 0.005)
    check("REPORT §7 warm s/60s", find(REPORT, r"warm \*\*(\d\.\d+) s\*\*"), lt["warm"], 0.005)
    clap = open(os.path.join(ROOT, "eval", "results", "clap.md")).read()
    cm = re.search(r"\*\*Matched\*\* mean (\d\.\d+).*?control\*\* mean (\d\.\d+)", clap, re.S)
    check("REPORT §4 CLAP matched", find(REPORT, r"mean \*\*(0\.\d+)\*\* \(sd"), float(cm.group(1)), 0.0005)
    check("REPORT §4 CLAP control", find(REPORT, r"every other prompt\): \*\*(0\.\d+)\*\*"), float(cm.group(2)), 0.0005)
    bl = open(os.path.join(ROOT, "eval", "results", "bleed.md")).read()
    bo = re.search(r"spectral overlap (\d\.\d+) \(band-split control (\d\.\d+)", bl)
    check("REPORT §5 spectral overlap", find(REPORT, r"shares \*\*(0\.\d+)\*\* of its spectrum"), float(bo.group(1)), 0.005)
    check("REPORT §5 band-split control", find(REPORT, r"against \*\*(0\.\d+)\*\* for a band-split"), float(bo.group(2)), 0.005)
    ac = list(csv.DictReader(open(os.path.join(EV, "eval", "approach_comparison.csv"))))
    check("REPORT §1 CLAP A vs B (A)", find(REPORT, r"\(0\.\d+ vs (0\.\d+), n = 5\)"), float(ac[0]["clap_mean"]), 0.0005)
    check("REPORT §1 CLAP A vs B (B)", find(REPORT, r"\((0\.\d+) vs 0\.\d+, n = 5\)"), float(ac[1]["clap_mean"]), 0.0005)
    tests = re.findall(r"\*\*(\d+) tests pass\*\*", REPORT) + re.findall(r"\((\d+) tests\)", REPORT)
    mt = open(os.path.join(EV, "integration", "make_test_output.txt")).read()
    passed = re.findall(r"(\d+) passed", mt)
    check("REPORT test count", [float(t) for t in tests], float(passed[-1]) if passed else -1, 0)
    readme_tests = find(README, r"(\d+) passed, 0 skipped")
    check("README test count", readme_tests, float(passed[-1]) if passed else -1, 0)
    return out


def paths():
    bad = []
    for name, doc in (("REPORT.md", REPORT), ("README.md", README)):
        for p in set(re.findall(r"\(([\w./-]+/[\w./-]*)\)", doc) + re.findall(r"`((?:src|tests|eval|evidence|testpack|docs|web|deploy|scripts)/[\w./*-]+)`", doc)):
            q = p.split("::")[0].rstrip("/")
            if re.fullmatch(r"[\d/.]+", q):  # ratios like 46/48, not paths
                continue
            if q.startswith(("http", "#")) or "*" in q or "<" in q:
                if "*" in q and not glob.glob(os.path.join(ROOT, q)):
                    bad.append(f"{name}: {p}")
                continue
            if not os.path.exists(os.path.join(ROOT, q)):
                bad.append(f"{name}: {p}")
    return bad


def declaration():
    v = json.load(open(os.path.join(EV, "verdicts.json")))
    sec = v.get("SECRETS", {})
    hashes = 0
    for d in glob.glob(os.path.join(EV, "runs", open(os.path.join(EV, "runs", "LATEST")).read().strip(), "*")):
        if os.path.exists(os.path.join(d, "files.json")) and os.path.exists(os.path.join(d, "music_manifest.json")):
            hashes += 1
    open(os.path.join(EV, "declaration_support.md"), "w").write(f"""# Support for 7_Declaration (you answer and sign; nothing here fills the sheet)

| Statement | Supporting evidence |
|---|---|
| Individual work; can explain and change any part | AI_USE.md lists exactly what the coding agent did; you must be able to walk through every module |
| Every claim true and backed by evidence | FORM_REPORT.md (every filled cell -> verdict -> files), evidence/INDEX.md, evidence/consistency.txt |
| All tools/models/APIs/libraries/data listed | SOURCES.md, licenses.yaml, eval/README.md, AI_USE.md, evidence/must_haves/mh4_licences/pip_licenses.csv |
| Default path and outputs licensed for commercial use | evidence/must_haves/mh4_licences/ (agpl_scan.txt, clause_check.csv); MinIO is compose/demo-only |
| No outputs edited by hand | {hashes} runs in the latest evidence run each have files.json (SHA-256 of every delivered file, as downloaded) next to the manifest and job id produced by the service; the audio pack is zipped from those downloads unchanged |
| No real person's voice/face/content used | the engine has no vocal programs and uses no recordings except the MIT SoundFont; narration in tests is synthetic noise ("speech-like" bursts) |
| No API keys or secrets in repo/logs/screenshots/form | {sec.get('evidence', ['evidence/security/secret_scan.txt'])[0]}: verdict {sec.get('verdict', 'NOT_RUN')}; presigned URL signatures are stripped from every committed JSON |
| Demo and links stay up until results | not provable in advance; needs your hosting + uptime monitor |

Commit: {git_sha()}
""")


if __name__ == "__main__":
    cs = checks()
    bp = paths()
    declaration()
    lines = [f"{'OK ' if c['ok'] else 'BAD'} {c['claim']}: doc {c['doc']} vs source {c['source']}" for c in cs]
    open(os.path.join(EV, "consistency.txt"), "w").write("\n".join(lines) + f"\n\nmissing paths quoted in docs: {bp or 'none'}\n")
    ok = all(c["ok"] for c in cs) and not bp
    verdict("CONSISTENCY", "meta", "consistency", "PASS" if ok else "FAIL",
            f"{sum(c['ok'] for c in cs)}/{len(cs)} quoted numbers match their sources; {len(bp)} missing paths",
            "; ".join(c["claim"] for c in cs if not c["ok"]) + ("; " + "; ".join(bp) if bp else ""),
            [rel(os.path.join(EV, "consistency.txt"))])
    print("\n".join(lines), "\nmissing paths:", bp)
