import type { JobState } from "../lib/types";

const TONE: Record<JobState, string> = { queued: "", running: "accent", succeeded: "ok", failed: "danger" };
const LABEL: Record<JobState, string> = { queued: "Queued", running: "Generating", succeeded: "Ready", failed: "Failed" };

export function StatusBadge({ status }: { status: JobState }) {
  const live = status === "queued" || status === "running";
  return <span className={`badge ${TONE[status] ? `badge--${TONE[status]}` : ""} ${live ? "badge--live" : ""}`}>{LABEL[status]}</span>;
}
