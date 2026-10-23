import type { MusicRequest } from "../../lib/types";

export interface SectionDraft {
  key: string;
  start: string;
  mood: string;
}

export interface Draft {
  prompt: string;
  duration: number;
  sections: SectionDraft[];
  tempo: string;
  key: string;
  seed: string;
  loopable: boolean;
  mp3: boolean;
  lufs: number;
  sampleRate: 44100 | 48000;
}

export const EMPTY_DRAFT: Draft = {
  prompt: "",
  duration: 30,
  sections: [],
  tempo: "",
  key: "",
  seed: "",
  loopable: false,
  mp3: true,
  lufs: -16,
  sampleRate: 48000,
};

const KEY = "score.draft";

export function loadDraft(): Draft {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? { ...EMPTY_DRAFT, ...JSON.parse(raw) } : EMPTY_DRAFT;
  } catch {
    return EMPTY_DRAFT;
  }
}

export function saveDraft(d: Draft) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(d));
  } catch {
    /* private mode: drafts just aren't kept */
  }
}

export function draftFromRequest(r: MusicRequest): Draft {
  return {
    ...EMPTY_DRAFT,
    prompt: r.prompt,
    duration: r.duration_s,
    sections: (r.sections ?? []).map((s, i) => ({ key: `s${i}`, start: String(s.start_s), mood: s.mood })),
    tempo: r.tempo_bpm ? String(r.tempo_bpm) : "",
    key: r.key ?? "",
    seed: r.seed !== undefined ? String(r.seed) : "",
    loopable: !!r.loopable,
    mp3: (r.output?.formats ?? []).includes("mp3"),
    lufs: r.output?.target_lufs ?? -16,
    sampleRate: r.output?.sample_rate ?? 48000,
  };
}

export type Errors = Partial<Record<"prompt" | "duration" | "tempo" | "seed" | "sections", string>>;

/** Mirrors the server's validation so most mistakes are caught before a round trip. */
export function validate(d: Draft): Errors {
  const e: Errors = {};
  if (!d.prompt.trim()) e.prompt = "Describe the music you want.";
  else if (d.prompt.length > 2000) e.prompt = "Keep the description under 2000 characters.";
  if (!(d.duration >= 5 && d.duration <= 300)) e.duration = "Length must be between 5 and 300 seconds.";
  if (d.tempo) {
    const t = Number(d.tempo);
    if (!Number.isFinite(t) || t < 40 || t > 200) e.tempo = "Tempo must be between 40 and 200 bpm.";
  }
  if (d.seed && !/^\d{1,10}$/.test(d.seed)) e.seed = "Use a whole number.";
  for (const s of d.sections) {
    const t = Number(s.start);
    if (s.start === "" || !Number.isFinite(t) || t < 0) {
      e.sections = "Every section needs a start time of 0 or more seconds.";
      break;
    }
    if (!s.mood.trim()) {
      e.sections = "Every section needs a mood, e.g. “calm intro”.";
      break;
    }
  }
  return e;
}

export function toRequest(d: Draft, narrationUrl?: string): MusicRequest {
  const req: MusicRequest = {
    prompt: d.prompt.trim(),
    duration_s: d.duration,
    loopable: d.loopable,
    output: { sample_rate: d.sampleRate, target_lufs: d.lufs, formats: d.mp3 ? ["wav", "mp3"] : ["wav"] },
  };
  if (d.sections.length)
    req.sections = d.sections
      .map((s) => ({ start_s: Number(s.start), mood: s.mood.trim() }))
      .sort((a, b) => a.start_s - b.start_s);
  if (d.tempo) req.tempo_bpm = Number(d.tempo);
  if (d.key) req.key = d.key;
  if (d.seed) req.seed = Number(d.seed);
  if (narrationUrl) req.narration_url = narrationUrl;
  return req;
}
