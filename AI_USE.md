# AI use

## In building this repository

- **Plan:** `IMPLEMENTATION_PLAN.md` (the design: approach choice, requirement traceability, algorithms, task list) was written before coding and given to a coding agent.
- **Code, tests and docs:** written by **Claude Code (Anthropic, model Claude Opus 5.5)** working from that plan, task by task (T0-T14). Each task was committed separately with its tests (`git log`). The agent also:
  - read the licence texts quoted in `SOURCES.md` (Debian copyright files for FluidR3_GM and FluidSynth, Debian's FFmpeg build rules, and installed package metadata);
  - ran the full test suite and the batch runner;
  - fixed the two defects that batch run 1 exposed (kept in `testpack/run1_failures/`).
- **What the agent could not do, and what remains human work:**
  - **Listening:** the agent cannot hear the audio. Prompt-to-music fit (T13 listening notes) must be judged by a person, and any claim about "sounds like X" is the human's call.
  - **Blind listening test** with ≥5 people (`eval/listening_test.md` holds the protocol and pack generator).
  - **Demo:** the demo deployment, the uptime monitor, the demo video and the submission form.
  - **Docker:** `docker compose` was not run (no Docker on the build machine). The same code was verified against native PostgreSQL, MinIO, FluidSynth and FFmpeg.
- **Review responsibility:** the submitter must read and be able to explain every module (the live session requires it). AI-written code is treated like any other contribution: tests, QA metrics and the batch run decide whether it works, not the author.

## In the product

- **Default path:** no AI model is involved. Music is composed by deterministic rules and templates (`composer/`, `styles/`) from a seed and rendered with sampled instruments. Nothing is trained on songs or copied from them.
- **Labelling:** every manifest has `"ai_generated": true` and an `ai_label` string, because the audio is machine-generated and should be disclosed as such wherever it is published.
- **Optional:** `INTERPRETER=llm` uses an LLM (Anthropic Messages API) only to map the prompt text to the same small JSON settings object (style, valence, energy, mode). It never generates audio. It is off by default, falls back to the rules interpreter on any failure (`LLM_UNAVAILABLE_RULES_USED`), and the provider and model appear in `manifest.providers[]`.
- **Evaluation:** `eval/` may use pretrained models (e.g. CLAP for prompt match; a text-to-music model plus source separation for the "Approach B" comparison). These run offline, only to measure, and are not in the service image.
