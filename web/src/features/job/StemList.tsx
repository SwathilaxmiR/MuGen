import { useState } from "react";
import { AudioTrack } from "../../components/AudioTrack";
import { Button } from "../../components/Button";
import { api, describeError } from "../../lib/api";
import { newKey, STEM_LABELS } from "../../lib/format";
import { navigate } from "../../lib/router";
import { addRecent } from "../../lib/storage";
import type { JobStatus, Manifest } from "../../lib/types";

export function StemList({ job, manifest }: { job: JobStatus; manifest: Manifest | null }) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const stems = job.result?.stems ?? {};

  async function regenerate(stem: string) {
    setBusy(stem);
    setError("");
    try {
      const res = await api.regenerate(job.job_id, stem, newKey());
      addRecent({
        id: res.job_id, prompt: manifest?.request.prompt ?? "Regenerated track", duration_s: manifest?.duration_s ?? 0,
        created: new Date().toISOString(), parent: job.job_id, stem,
      });
      navigate(`/jobs/${res.job_id}`);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      {Object.entries(stems).map(([name, url]) => {
        const meta = manifest?.stems.find((s) => s.name === name);
        return (
          <AudioTrack key={name} title={STEM_LABELS[name] ?? name} subtitle={meta?.program_name} src={url}
            downloadName={`${name}.wav`}
            actions={
              <Button variant="ghost" size="sm" loading={busy === name} disabled={!!busy && busy !== name}
                onClick={() => regenerate(name)} aria-label={`Regenerate ${STEM_LABELS[name] ?? name}`}
                title="Makes a new version with a fresh take on this part; the other stems stay identical">
                Regenerate
              </Button>
            } />
        );
      })}
      {error && <p className="field__error" role="alert">{error}</p>}
      <p className="field__hint">Regenerate writes a fresh take of one part into a new version. The other three stay
        identical, byte for byte.</p>
    </div>
  );
}
