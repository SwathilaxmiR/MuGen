"""E6/E7: fill the submission workbook from evidence/verdicts.json, then write FORM_REPORT.md and evidence/INDEX.md.

    python scripts/fill_form.py            # -> Assessment1_<Name>.xlsx (git-ignored), FORM_REPORT.md, evidence/INDEX.md

Only whitelisted cells are written. A "Yes" needs every evidence path tracked by git at HEAD (or a live URL);
otherwise it is downgraded and the reason is reported. Human-only cells stay empty unless supplied in
evidence/form_inputs.yaml (git-ignored: it holds personal details and the demo token).
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import openpyxl
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EV = os.path.join(ROOT, "evidence")
BLANK = os.path.join(EV, "form", "blank_form.xlsx")
VERDICTS = json.load(open(os.path.join(EV, "verdicts.json")))
FI = yaml.safe_load(open(os.path.join(EV, "form_inputs.yaml"))) if os.path.exists(os.path.join(EV, "form_inputs.yaml")) else {}

WHITELIST = {
    "1_Your_Details": [f"B{r}" for r in range(4, 19)],
    "2_Must_haves": [f"{c}{r}" for r in range(6, 12) for c in "CDE"],
    "3_Levels": [f"{c}{r}" for r in range(5, 16) for c in "CDE"],
    "4_Integration": [f"{c}{r}" for r in range(5, 15) for c in "CD"],
    "5_Metrics": [f"{c}{r}" for r in range(5, 11) for c in "CDE"],
    "6_Hard_cases": [f"{c}{r}" for r in range(5, 13) for c in "CDE"],
}
HUMAN_DETAILS = {"B4": "name", "B5": "email", "B6": "phone", "B7": "college_degree", "B8": "graduation_year",
                 "B13": "video_url", "B18": "hours"}
YES_NO_SHEETS = {"2_Must_haves", "6_Hard_cases"}


def tracked() -> set[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=ROOT).stdout.split()
    s = set(out)
    for f in out:  # directories that contain tracked files
        parts = f.split("/")
        for i in range(1, len(parts)):
            s.add("/".join(parts[:i]))
    return s


def evidence_ok(paths: list[str], tr: set[str]) -> list[str]:
    bad = []
    for p in paths:
        if p.startswith(("http://", "https://")):
            try:
                import httpx

                if httpx.get(p, timeout=10, follow_redirects=True).status_code >= 300:
                    bad.append(p)
            except Exception:  # noqa: BLE001
                bad.append(p)
        elif p.startswith("VIDEO@"):
            if not FI.get("video_timestamps", {}).get(p):
                bad.append(p)
        elif p.rstrip("/") not in tr:
            bad.append(p)
    return bad


def map_verdict(v: str, sheet: str) -> str | None:
    if v == "PASS":
        return "Yes"
    if v == "PARTIAL":
        return "No" if sheet in YES_NO_SHEETS else "Partial"
    if v in ("FAIL", "NOT_RUN"):
        return "No"
    return None  # PENDING_HUMAN / HUMAN -> leave empty


def links(e: list[str]) -> str:
    out = []
    for p in e[:3]:
        out.append(f"{p} (demo video {FI['video_timestamps'][p]})" if p.startswith("VIDEO@") and FI.get("video_timestamps", {}).get(p) else p)
    return " ; ".join(out)


def main():
    tr = tracked()
    wb = openpyxl.load_workbook(BLANK)  # keeps formulas and data validations
    written, downgraded, pending, cannot = [], [], [], []

    def put(sheet, cell, value, source):
        assert cell in WHITELIST[sheet], (sheet, cell)
        wb[sheet][cell] = value
        written.append({"cell": f"{sheet}!{cell}", "value": value, "source": source})

    # personal details: only from form_inputs.yaml
    for cell, k in HUMAN_DETAILS.items():
        if FI.get(k):
            put("1_Your_Details", cell, FI[k], "form_inputs.yaml (human)")
        else:
            pending.append(f"1_Your_Details!{cell} ({k})")
    if FI.get("demo_token"):
        put("1_Your_Details", "B10", FI["demo_token"], "form_inputs.yaml (human; never committed)")
    for key, v in VERDICTS.items():
        sheet, cell = v["sheet"], v["cell"]
        if sheet not in WHITELIST:
            continue
        ev = v["evidence"]
        if sheet == "1_Your_Details":
            if v["verdict"] == "PASS" or (v["verdict"] == "HUMAN" and v["value"] and key in ("D_PAID", "D_AI_TOOLS")):
                put(sheet, cell, v["value"], key)
                if v["verdict"] == "HUMAN":
                    pending.append(f"{sheet}!{cell}: confirm '{v['value'][:70]}'")
            else:
                pending.append(f"{sheet}!{cell}: {v['note'] or v['value']}")
            continue
        row = cell[1:]
        val = map_verdict(v["verdict"], sheet)
        bad = evidence_ok(ev, tr) if val == "Yes" else []
        if bad:
            val = "No" if sheet in YES_NO_SHEETS else "Partial"
            downgraded.append(f"{sheet}!{cell} ({key}): evidence not committed / not reachable: {bad}")
        if sheet == "5_Metrics":
            put(sheet, f"C{row}", v["value"] if v["verdict"] in ("PASS", "PARTIAL") else "Not measured", key)
            put(sheet, f"D{row}", v["note"], key)
            put(sheet, f"E{row}", links(ev), key)
            if v["verdict"] != "PASS":
                cannot.append(f"{sheet}!C{row} ({key}): {v['verdict']} {v['value']}")
            continue
        if val is None:
            pending.append(f"{sheet}!C{row} ({key}): {v['verdict']} - {v['note']}")
            put(sheet, f"D{row}", links(ev), key)
            continue
        put(sheet, f"C{row}", val, key)
        put(sheet, f"D{row}", (v["note"] if sheet == "6_Hard_cases" else links(ev)), key)
        if sheet == "6_Hard_cases":
            put(sheet, f"E{row}", links(ev), key)
        elif sheet in ("2_Must_haves", "3_Levels"):
            e = v["value"] + (f". {v['note']}" if v["note"] else "")
            put(sheet, f"E{row}", (e if sheet == "2_Must_haves" else f"{e}. Reproduce: make evidence")[:1000], key)
        if val != "Yes":
            cannot.append(f"{sheet}!C{row} ({key}): {val} - {v['value']} - {v['note']}")
    wb.calculation.fullCalcOnLoad = True  # Excel/LibreOffice recompute the GREEN cells on open
    name = (FI.get("name") or "YourName").replace(" ", "")
    out = os.path.join(ROOT, f"Assessment1_{name}.xlsx")
    wb.save(out)
    check = self_check(out)
    verify_only_whitelist(out)
    report(out, written, downgraded, pending, cannot, check)
    print(f"wrote {out}\n{check}")


def self_check(path: str) -> dict:
    """LibreOffice is not installed here, so the GREEN formulas are evaluated with the same logic in Python."""
    wb = openpyxl.load_workbook(path)

    def col(sheet, rng):
        ws = wb[sheet]
        return [ws[f"C{r}"].value for r in range(rng[0], rng[1] + 1)]

    mh = col("2_Must_haves", (6, 11))
    lv = col("3_Levels", (5, 15))
    it = col("4_Integration", (5, 14))
    core, adv, out = lv[0:3].count("Yes") == 3, lv[3:8].count("Yes") == 5, lv[8:11].count("Yes") == 3
    level = "Outstanding" if core and adv and out else "Advanced" if core and adv else "Core" if core else "None"
    marks = {"Outstanding": 40, "Advanced": 30, "Core": 15, "None": 0}[level]
    integ = it.count("Yes") * 2 + it.count("Partial")
    return {"must_haves_yes": f"{mh.count('Yes')} of 6", "level": level, "level_marks": marks,
            "integration_marks": integ, "self_assessed_total_60": marks + integ,
            "formula_check": wb["3_Levels"]["C17"].value[:40] + "...",
            "note": "computed in Python (LibreOffice not installed); Excel recalculates on open (fullCalcOnLoad)"}


def verify_only_whitelist(path: str):
    a, b = openpyxl.load_workbook(BLANK), openpyxl.load_workbook(path)
    for ws in a.worksheets:
        wb2 = b[ws.title]
        for row in ws.iter_rows(min_row=1, max_row=max(ws.max_row, wb2.max_row), max_col=max(ws.max_column, wb2.max_column)):
            for c in row:
                v2 = wb2[c.coordinate].value
                if c.value != v2:
                    assert c.coordinate in WHITELIST.get(ws.title, []), f"non-whitelisted change {ws.title}!{c.coordinate}"
        dv1 = sorted(str(d.sqref) + str(d.formula1) for d in ws.data_validations.dataValidation)
        dv2 = sorted(str(d.sqref) + str(d.formula1) for d in wb2.data_validations.dataValidation)
        assert dv1 == dv2, f"data validation changed on {ws.title}"
        for r in ws.iter_rows():
            for c in r:
                if isinstance(c.value, str) and c.value.startswith("="):
                    assert wb2[c.coordinate].value == c.value, f"formula changed {ws.title}!{c.coordinate}"
    for title, cells in WHITELIST.items():
        for coord in cells:
            v = b[title][coord].value
            if coord.startswith("C") and title in ("2_Must_haves", "6_Hard_cases") and v is not None:
                assert v in ("Yes", "No"), (title, coord, v)
            if coord.startswith("C") and title in ("3_Levels", "4_Integration") and v is not None:
                assert v in ("Yes", "Partial", "No"), (title, coord, v)


def report(out, written, downgraded, pending, cannot, check):
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    run = open(os.path.join(EV, "runs", "LATEST")).read().strip()
    L = [f"# FORM_REPORT\n\nGenerated {datetime.now(timezone.utc).isoformat(timespec='seconds')} from "
         f"`evidence/verdicts.json` (evidence run `{run}`, commit `{sha[:12]}`) by `scripts/fill_form.py`. "
         f"Output: `{os.path.basename(out)}` (git-ignored).\n",
         "## Self-check (the form's GREEN cells)\n", "| | |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in check.items()]
    L += ["\n## Every filled cell\n", "| cell | value | verdict key | evidence |", "|---|---|---|---|"]
    for w in written:
        v = VERDICTS.get(w["source"], {})
        L.append(f"| {w['cell']} | {str(w['value'])[:140].replace('|', '/')} | {w['source']} | "
                 f"{'; '.join(v.get('evidence', [])[:3]) if v else ''} |")
    L += ["\n## Needs a human\n"] + [f"- {p}" for p in pending] + [
        "- Listening checks: fill `evidence/listening/log.csv` (clips in `evidence/listening/clips/`)",
        "- Blind test with >= 5 people: put responses in `evidence/eval/blind_test/responses.csv` (columns listener, pair, preferred = ours/baseline/none, comment)",
        "- Demo video from `evidence/demo/demo_script.md`; put the timestamps in `evidence/form_inputs.yaml`",
        "- 7_Declaration (all 8 answers, signature, date): see `evidence/declaration_support.md`",
        "- Then: commit evidence, `make evidence-form`, check this list is empty, tag `submission-v1`"]
    L += ["\n## Cannot claim (FAIL / NOT_RUN / PARTIAL)\n"] + ([f"- {c}" for c in cannot] or ["- none"])
    L += ["\n## Downgraded by the filler\n"] + ([f"- {d}" for d in downgraded] or ["- none"])
    L += ["\n## Claims at risk\n",
          "- 3_Levels row 6 'obviously matches the description' is judged by listening; CLAP agreement is modest "
          "(see 5_Metrics row 10).",
          "- 2_Must_haves row 6: the demo must stay up for the whole review; nothing here proves future uptime.",
          "- Docker: `make up` / `make test` have never run on this machine. Run them once on a Docker host before "
          "claiming Integration 1 as Yes.",
          "- Measurements come from a fanless laptop; throughput varies under sustained load (eval/results/loadtest*.jsonl).",
          "- The click detector threshold (ratio 3.0) was raised after evidence run ev1 flagged a drum fill as a click."]
    open(os.path.join(ROOT, "FORM_REPORT.md"), "w").write("\n".join(L) + "\n")
    I = ["# Evidence index (claim -> files)\n", f"Run `{run}`, commit `{sha[:12]}`. Regenerate: `make evidence`.\n",
         "| claim (form cell) | verdict | value | evidence |", "|---|---|---|---|"]
    for k, v in sorted(VERDICTS.items(), key=lambda kv: (kv[1]["sheet"], kv[1]["cell"])):
        I.append(f"| {v['sheet']}!{v['cell']} ({k}) | {v['verdict']} | {v['value'][:110].replace('|', '/')} | "
                 f"{'<br>'.join(v['evidence'])} |")
    I += ["\n## REPORT.md claims\n", "| REPORT.md section | evidence |", "|---|---|",
          "| 3 Must-haves measured | evidence/must_haves/*, evidence/metrics/loudness_table.csv |",
          "| 4 Prompt match | evidence/eval/clap.csv, eval/results/clap.md |",
          "| 5 Stem cleanliness | evidence/metrics/stem_quality.csv, eval/results/bleed.md |",
          "| 6 Approach B | evidence/eval/approach_comparison.md |",
          "| 7 Production numbers | evidence/metrics/speed.csv, load.csv, costs.json |",
          "| 7a Failures found | evidence/runs/ev1/duration_120s/, testpack/run1_failures/ |"]
    open(os.path.join(EV, "INDEX.md"), "w").write("\n".join(I) + "\n")


if __name__ == "__main__":
    sys.exit(main())
