import type { JobStatus } from "../../lib/types";

// Worker progress milestones (worker/pipeline.py): 5 interpret, 10 plan, 20-70 render stems, 80 mix, 85 ducking, 95 QA/upload.
export const STAGES = [
  { label: "Waiting for a free worker", until: 1 },
  { label: "Reading the prompt and planning", until: 15 },
  { label: "Composing and rendering four stems", until: 72 },
  { label: "Mixing, mastering and checking", until: 90 },
  { label: "Saving files", until: 100 },
];

export function stageIndex(job: JobStatus): number {
  if (job.status === "queued") return 0;
  if (job.status === "succeeded") return STAGES.length;
  const i = STAGES.findIndex((s) => job.progress < s.until);
  return i === -1 ? STAGES.length - 1 : Math.max(1, i);
}
