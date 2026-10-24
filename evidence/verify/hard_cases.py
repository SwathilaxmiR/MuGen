"""6_Hard_cases rows 5-12: one folder per hard case with request, result, warnings and the test that covers it."""
import json
import os
import shutil

from common import EV, cases, out_dir, rel, runs_dir, verdict  # noqa: E402


def collect(hc: str, names: list[str], test_ref: str) -> tuple[list, str]:
    d = out_dir("hard_cases", hc)
    found = []
    for name in names:
        src = os.path.join(runs_dir(), name)
        if not os.path.isdir(src):
            continue
        st = json.load(open(os.path.join(src, "status.json")))
        req = json.load(open(os.path.join(src, "request.json")))
        man = json.load(open(os.path.join(src, "music_manifest.json"))) if os.path.exists(os.path.join(src, "music_manifest.json")) else None
        sub = os.path.join(d, name)
        os.makedirs(sub, exist_ok=True)
        shutil.copy(os.path.join(src, "request.json"), os.path.join(sub, "request.json"))
        result = {"job_id": st["job_id"], "status": st["status"], "error": st.get("error"),
                  "duration_s": man and man["duration_s"], "style": man and man["style"],
                  "tempo_bpm": man and man["tempo_bpm"], "hit_time_s": man and man["hit_time_s"],
                  "sections": man and [(s["mood"], s["applied_start_s"]) for s in man["sections"]],
                  "stems": man and [s["program_name"] for s in man["stems"]],
                  "timings_total_s": man and man["timings_s"]["total"],
                  "manifest": rel(os.path.join(src, "music_manifest.json")) if man else None}
        json.dump(result, open(os.path.join(sub, "result.json"), "w"), indent=2, ensure_ascii=False)
        open(os.path.join(sub, "warnings.txt"), "w").write(
            "\n".join(f"{w['code']}: {w['message']}" for w in st["warnings"]) + "\n")
        found.append({"name": name, "status": st, "request": req, "manifest": man})
    open(os.path.join(d, "test_ref.txt"), "w").write(test_ref + "\n")
    return found, rel(d)


def codes(f):
    return {w["code"] for w in f["status"]["warnings"]}


def main():
    meta = json.load(open(os.path.join(runs_dir(), "run_meta.json")))
    sp = meta["special"]

    f, d = collect("hc1", ["hard_5s", "hard_6s", "hard_300s"], "tests/unit/test_timegrid.py (D in 5, 5.5, 6, 300); "
                   "tests/e2e/test_e2e.py::test_hard_cases[hard_short_5s|hard_long_300s]")
    ok = len(f) == 3 and all(x["status"]["status"] == "succeeded" for x in f)
    by = {x["name"]: x for x in f}
    t300 = by["hard_300s"]["manifest"]["timings_s"]["total"] if "hard_300s" in by else None
    verdict("HC1", "6_Hard_cases", "C5", "PASS" if ok else "FAIL",
            "Yes" if ok else "No",
            f"5-6 s: one section, 1-2 bars with the final hit on a bar line (hit {by.get('hard_5s', {}).get('manifest', {}).get('hit_time_s')} s "
            f"in a 5 s track), exact length. 300 s: same path, default intro/build/peak arc, generated in {t300} s.",
            [d], {"cell_D": True})

    f, d = collect("hc2", ["hard_vague", "hard_contradictory"], "tests/unit/test_interpreter.py::test_vague_defaults, test_contradiction_resolved")
    ok = len(f) == 2 and "VAGUE_PROMPT_DEFAULTS" in codes(f[0]) and "CONTRADICTORY_PROMPT" in codes(f[1])
    verdict("HC2", "6_Hard_cases", "C6", "PASS" if ok else "FAIL", "Yes" if ok else "No",
            "Vague ('music'): neutral corporate preset at moderate energy, VAGUE_PROMPT_DEFAULTS. Contradictory "
            "('calm but aggressive'): mid energy, minor mode, slow-to-mid tempo, percussive 'tense' preset, "
            "CONTRADICTORY_PROMPT stating the resolution.", [d])

    f, d = collect("hc3", ["hard_named_song", "hard_named_song_cover", "hard_vocals", "hard_vocals_choir"],
                   "tests/unit/test_interpreter.py::test_named_song_stripped, test_vocals_stripped_and_warned; "
                   "tests/unit/test_composer.py::test_forbidden_programs_never_used")
    named = [x for x in f if x["name"].startswith("hard_named")]
    voc = [x for x in f if x["name"].startswith("hard_vocals")]
    ok = named and voc and all("NAMED_WORK_IGNORED" in codes(x) for x in named) and all("VOCALS_NOT_SUPPORTED" in codes(x) for x in voc)
    verdict("HC3", "6_Hard_cases", "C7", "PASS" if ok else "FAIL", "Yes" if ok else "No",
            "Song/artist references ('like Interstellar by Hans Zimmer', quoted titles, 'cover of') are removed before "
            "planning and only generic mood words are used (NAMED_WORK_IGNORED); vocal requests are stripped and the "
            "output stays instrumental with no voice programs (VOCALS_NOT_SUPPORTED). No song data is used.", [d])

    f, d = collect("hc4", ["sections_close", "sections_after_end"], "tests/unit/test_sections.py::test_merge_min_gap_keeps_earlier_start_and_higher_intensity, test_section_after_end_dropped")
    ok = len(f) == 2 and "SECTIONS_MERGED_MIN_GAP" in codes(f[0]) and "SECTION_AFTER_END_DROPPED" in codes(f[1])
    verdict("HC4", "6_Hard_cases", "C8", "PASS" if ok else "FAIL", "Yes" if ok else "No",
            "After snapping to the beat, sections < 1.5 s apart are merged (earlier start, higher intensity, "
            "SECTIONS_MERGED_MIN_GAP); a section starting at or after one beat before the final hit is dropped "
            "(SECTION_AFTER_END_DROPPED).", [d])

    f, d = collect("hc5", ["narration_long_silences", "narration_gaps", "narration_no_speech"],
                   "tests/unit/test_ducking.py::test_long_silences_return_to_full_level, test_all_silence; "
                   "evidence/levels/adv_ducking/depth.csv")
    nos = [x for x in f if x["name"] == "narration_no_speech"]
    ok = len(f) == 3 and nos and "NARRATION_NO_SPEECH" in codes(nos[0])
    verdict("HC5", "6_Hard_cases", "C9", "PASS" if ok else "FAIL", "Yes" if ok else "No",
            "Speech is detected with an energy VAD; in silences of 1 s or more the music returns to full level "
            "(500 ms release, curve in the manifest); gaps < 0.6 s are bridged so it does not pump. With no speech at "
            "all mix_ducked.wav equals the mix and NARRATION_NO_SPEECH is returned.", [d, "evidence/levels/adv_ducking/depth.csv"])

    f, d = collect("hc6", ["hard_spanish", "hard_hindi", "hard_tamil", "hard_unknown_language"],
                   "tests/unit/test_interpreter.py::test_non_english, test_unknown_language_falls_back")
    langs = {x["name"]: next((w.get("details", {}).get("language") for w in x["status"]["warnings"]
                              if w["code"] in ("PROMPT_TRANSLATED", "PROMPT_LANGUAGE_FALLBACK")), None) for x in f}
    ok = len(f) == 4 and all("PROMPT_TRANSLATED" in codes(x) for x in f if x["name"] != "hard_unknown_language") \
        and any("PROMPT_LANGUAGE_FALLBACK" in codes(x) for x in f if x["name"] == "hard_unknown_language")
    verdict("HC6", "6_Hard_cases", "C10", "PASS" if ok else "FAIL", "Yes" if ok else "No",
            f"Language is detected (script ranges + langdetect: {langs}); es/fr/de/pt/hi/ta/ja/zh mood and genre words are "
            "mapped with a built-in lexicon (PROMPT_TRANSLATED); an unknown language falls back to neutral defaults "
            "(PROMPT_LANGUAGE_FALLBACK).", [d])

    conc = sp.get("concurrency", {})
    sk = sp.get("same_key", {})
    d = out_dir("hard_cases", "hc7")
    json.dump({"concurrency": conc, "same_key": sk}, open(os.path.join(d, "result.json"), "w"), indent=2)
    open(os.path.join(d, "test_ref.txt"), "w").write("tests/integration/test_api.py::test_idempotency_parallel_identical_requests_make_one_job; "
                                                    "tests/integration/test_worker.py::test_two_jobs_claimed_independently; tests/e2e/test_e2e.py::test_concurrent_jobs\n")
    ok = conc.get("all_succeeded") and conc.get("distinct_job_ids") == len(conc.get("jobs", [])) \
        and len(set(sk.get("sequential", []))) == 1 and len(set(sk.get("parallel", []))) == 1 \
        and sk.get("sequential_job_started_events") == 1
    verdict("HC7", "6_Hard_cases", "C11", "PASS" if ok else "FAIL", "Yes" if ok else "No",
            f"{len(conc.get('jobs', []))} jobs sent at the same moment are claimed independently (FOR UPDATE SKIP LOCKED) and "
            "all complete; the same request with the same Idempotency-Key (twice in a row and twice in parallel) returns "
            "the same job_id and the work runs once; a different body with that key gets 409 IDEMPOTENCY_KEY_REUSED.",
            [rel(d)])

    faults = sp.get("faults", {})
    d = out_dir("hard_cases", "hc8")
    json.dump(faults, open(os.path.join(d, "result.json"), "w"), indent=2, default=str)
    for name in ("fault_render_primary_fail", "fault_render_timeout", "fault_no_fallback", "worker_kill"):
        if os.path.isdir(os.path.join(runs_dir(), name)):
            shutil.copytree(os.path.join(runs_dir(), name), os.path.join(d, name), dirs_exist_ok=True)
    open(os.path.join(d, "test_ref.txt"), "w").write("tests/unit/test_renderer.py::test_primary_failure_falls_back_with_warning, "
                                                    "test_timeout_retries_then_falls_back, test_all_renderers_fail_is_render_failed; "
                                                    "tests/integration/test_worker.py::test_killed_worker_job_is_requeued_and_completes\n")
    if isinstance(faults, str):
        verdict("HC8", "6_Hard_cases", "C12", "NOT_RUN", "No", faults, [rel(d)])
    else:
        fb = all("PROVIDER_FALLBACK_USED" in (faults.get(k, {}).get("warnings") or "")
                 and faults.get(k, {}).get("status") == "succeeded" for k in ("render_primary_fail", "render_timeout"))
        nf = faults.get("no_fallback", {})
        nf_ok = nf.get("status") == "failed"
        wk = faults.get("worker_kill", {})
        wk_ok = wk.get("final_status") == "succeeded" and (wk.get("attempts") or 0) >= 2
        err = json.load(open(os.path.join(runs_dir(), "fault_no_fallback", "status.json")))["error"] if nf_ok else None
        ok = fb and nf_ok and err and err["code"] == "RENDER_FAILED" and err["retryable"] and wk_ok
        verdict("HC8", "6_Hard_cases", "C12", "PASS" if ok else "FAIL", "Yes" if ok else "No",
                "Renderer error or timeout: the stem is retried once, then rendered by the built-in numpy synth "
                "(PROVIDER_FALLBACK_USED, job succeeds); if every renderer fails the job fails RENDER_FAILED "
                f"(retryable). A worker killed mid-job: heartbeat goes stale, the job is re-queued and completes "
                f"(attempts {wk.get('attempts')}).", [rel(d)])


if __name__ == "__main__":
    main()
