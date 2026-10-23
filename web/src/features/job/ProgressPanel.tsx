import { Card } from "../../components/Card";
import { ProgressBar } from "../../components/ProgressBar";
import type { JobStatus } from "../../lib/types";
import { STAGES, stageIndex } from "./stages";

export function ProgressPanel({ job }: { job: JobStatus }) {
  const active = stageIndex(job);
  return (
    <Card title="Making your track" aside={<span className="muted mono">{job.progress}%</span>}>
      <div className="stack">
        <ProgressBar value={job.status === "queued" ? null : job.progress} label="Generation progress" />
        <ol className="steps" aria-live="polite">
          {STAGES.map((s, i) => (
            <li key={s.label} data-state={i < active ? "done" : i === active ? "active" : "todo"}
              aria-current={i === active ? "step" : undefined}>
              {s.label}
            </li>
          ))}
        </ol>
        <p className="field__hint">You can leave this page. The track keeps generating and stays in your Library.</p>
      </div>
    </Card>
  );
}
