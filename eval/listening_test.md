# Blind listening test (human task, not yet run)

**Status:** the pack generator and protocol are ready. The test itself needs real listeners and has **not been run**. No preference numbers exist yet, and REPORT.md says so.

## Design

- **Comparison:** ours vs a simple baseline. The baseline is one GM acoustic piano playing I-V-vi-IV block chords at a fixed 100 bpm in C major, looped, hard-trimmed to the same length, with no sections, normalised to the same −16 LUFS.
- **Prompts:** 6, covering cinematic, lo-fi, EDM, tense, playful and jazz (`eval/make_listening_pack.py: CASES`).
- **Order:** A/B is randomised per pair (seed 2026). The answer key is written to a separate folder that listeners never see.
- **Listeners:** ≥ 5 people who did not build the system. Use headphones or decent speakers, at a comfortable fixed volume.
- **Question per pair:** "Which one fits the prompt better as background music?" Answers are A / B / no preference, plus an optional comment.

## Steps

```bash
python eval/make_listening_pack.py --batch out/batch3 --out out/listening_pack
# share out/listening_pack/ (6 pairs + FORM.md) via a form with audio links; keep out/listening_key/ private
```

1. Make a form (Google Forms, Typeform…) with one question per pair, copied from `FORM.md`, with the two audio links.
2. Collect at least 5 complete responses. Record the date and how listeners were recruited.
3. Un-blind with `out/listening_key/answer_key.csv` and record, per pair and overall:
   - n;
   - the preference rate for ours, counting "no preference" separately;
   - a binomial sign-test p-value over non-tied answers;
   - every comment, including the ones where the baseline won.
4. Put the table in REPORT.md under "Blind listening test", replacing the "not run" note.

## Results template

| pair | prompt | ours preferred | baseline preferred | no preference | comments |
|---|---|---|---|---|---|
| 1 | … | | | | |

Overall: n = …, ours preferred in …/… non-tied answers (…%), sign test p = ….

Note the independent automatic proxy that already exists: CLAP scores ours above the baseline on 6/6 of these prompts (`eval/results/clap.md`). It does not replace this test.
