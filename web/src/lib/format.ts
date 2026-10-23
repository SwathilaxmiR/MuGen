export function formatDuration(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s - m * 60;
  const secStr = Number.isInteger(sec) ? String(sec) : sec.toFixed(1);
  return m ? `${m}:${secStr.padStart(Number.isInteger(sec) ? 2 : 4, "0")}` : `${secStr} s`;
}

export function relativeTime(iso: string, now = Date.now()): string {
  const diff = Math.round((now - new Date(iso).getTime()) / 1000);
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export const STEM_LABELS: Record<string, string> = {
  drums: "Drums",
  bass: "Bass",
  harmony: "Harmony",
  melody: "Melody",
};

/** Human copy for warning codes (README.md, "Warning codes"). Unknown codes fall back to the server text. */
export const WARNING_TITLES: Record<string, string> = {
  CONTRADICTORY_PROMPT: "Mixed signals in the prompt",
  NAMED_WORK_IGNORED: "Song or artist reference removed",
  VOCALS_NOT_SUPPORTED: "Instrumental only",
  PROMPT_TRANSLATED: "Prompt translated",
  PROMPT_LANGUAGE_FALLBACK: "Language not understood",
  VAGUE_PROMPT_DEFAULTS: "Prompt was vague",
  SECTIONS_MERGED_MIN_GAP: "Sections merged",
  SECTION_AFTER_END_DROPPED: "Section dropped",
  SECTION_SNAPPED: "Section moved to the beat",
  TEMPO_ADJUSTED_FOR_LOOP: "Tempo adjusted for the loop",
  TEMPO_OUTSIDE_SNAP_RANGE: "Very slow tempo",
  ENDING_ON_BEAT_NOT_BAR: "Ending lands on a beat",
  NARRATION_NO_SPEECH: "No speech in narration",
  NARRATION_FETCH_FAILED: "Narration unavailable",
  NARRATION_TRUNCATED: "Narration longer than music",
  PROVIDER_FALLBACK_USED: "Backup renderer used",
  LLM_UNAVAILABLE_RULES_USED: "Standard interpreter used",
  LOOP_IGNORES_ENDING: "Loop has no ending",
  REGEN_STEM_TRIMMED: "New stem lowered slightly",
};

export function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
