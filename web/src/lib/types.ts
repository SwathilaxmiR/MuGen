// Mirrors src/musicengine/schemas.py and music_manifest.json (only the fields the UI reads).

export type JobState = "queued" | "running" | "succeeded" | "failed";
export type StemName = "drums" | "bass" | "harmony" | "melody";

export interface SectionInput {
  start_s: number;
  mood: string;
}

export interface MusicRequest {
  prompt: string;
  duration_s: number;
  sections?: SectionInput[];
  tempo_bpm?: number;
  key?: string;
  loopable?: boolean;
  narration_url?: string;
  seed?: number;
  output?: { sample_rate?: 44100 | 48000; target_lufs?: number; formats?: ("wav" | "mp3")[] };
}

export interface Warning {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ErrorInfo {
  code: string;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown>;
}

export interface JobResult {
  mix_wav: string;
  mix_mp3: string | null;
  stems: Record<string, string>;
  mix_ducked: string | null;
  manifest: string;
}

export interface JobStatus {
  job_id: string;
  status: JobState;
  progress: number;
  kind: "generate" | "regenerate";
  parent_job_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  warnings: Warning[];
  result: JobResult | null;
  error: ErrorInfo | null;
}

export interface ManifestSection {
  applied_start_s: number;
  requested_start_s: number | null;
  mood: string;
  intensity: number;
}

export interface Manifest {
  job_id: string;
  style: string;
  tempo_bpm: number;
  key: { name: string };
  duration_s: number;
  sample_rate: number;
  hit_time_s: number | null;
  loop: { enabled: boolean };
  sections: ManifestSection[];
  stems: { name: string; program_name: string; renderer: string }[];
  loudness: { integrated_lufs: number; true_peak_dbtp: number; target_lufs: number };
  qa: { passed: boolean; length_error_s: number; sum_diff_db: number; clicks: number; gaps: number };
  ducking: { applied: boolean; depth_db: number | null; segments: { start_s: number; end_s: number }[] };
  timings_s: { total: number };
  request: MusicRequest;
}
