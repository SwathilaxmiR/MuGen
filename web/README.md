# Score: web UI for the music engine

React 18 + TypeScript + Vite. The only runtime dependencies are `react` and `react-dom`.

## Run

```bash
# 1. start the API + worker (see the root README), listening on :8000
# 2. then:
cd web
npm install
npm run dev          # http://localhost:5173; /api, /ready and /docs are proxied to :8000
```

**Production.** Run `npm run build`. The API then serves `web/dist` at `/` automatically, on the same origin, so no CORS setup is needed. To use another location, set `WEB_DIST_DIR`. Any static host also works if it proxies `/api` to the API. To point at a different API in development, set `VITE_API_PROXY`. For a separate origin at build time, set `VITE_API_BASE`.

| Command | What it does |
|---|---|
| `npm run typecheck` | `tsc` with strict settings |
| `npm test` | vitest unit tests for validation, request building, routing and formatting |
| `npm run build` | Typecheck, then build to `dist/` |

## Screens

- **New track** (`#/`):
  - prompt with example chips;
  - length slider plus presets;
  - optional mood sections;
  - narration upload (adds a ducked mix);
  - a collapsed "Fine-tune" panel: tempo, key, seed, loudness, sample rate, loop, MP3.

  Validation mirrors the server's rules.
- **Track** (`#/jobs/<id>`):
  - live progress with stages;
  - when it's ready: the mix player, the ducked mix, a section timeline, the four stems each with *Regenerate*, facts (style, tempo, key, LUFS, true peak), notes for each server warning, and downloads;
  - when it fails: the error, plus *Edit and try again*, which pre-fills the form.
- **Library** (`#/library`): tracks started from this browser.

## Structure

```
src/
  components/      Button, Field (label/hint/error wiring), Card, Badge, ProgressBar, AudioTrack,
                   Notice, Facts, Dialog (native <dialog>), Header, SettingsDialog
  features/create/ CreatePage, SectionsEditor, draft.ts (form state, validation, request mapping)
  features/job/    JobPage, ProgressPanel, StemList, Timeline, stages.ts
  features/        LibraryPage
  lib/             api.ts (typed client + error copy), types.ts, useJob.ts (polling), router.ts (hash router),
                   storage.ts (token + recent jobs), format.ts
  styles/app.css   design tokens (light/dark), layout, components
```

## Accessibility

Checked with axe-core in Chrome (light, dark and mobile; job and library pages): 0 violations. The UI also provides:
- semantic landmarks, a skip link, and focus moved to the content on navigation;
- every control has a label, with hints and errors linked through `aria-describedby`;
- the progress bar uses `role="progressbar"`, and stages are announced politely;
- native `<audio>` controls and a native `<dialog>` (focus trap, Esc to close);
- `prefers-reduced-motion` is respected, and there is no horizontal scroll at 390 px.
