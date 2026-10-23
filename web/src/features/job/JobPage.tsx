import { AudioTrack } from "../../components/AudioTrack";
import { StatusBadge } from "../../components/Badge";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Facts } from "../../components/Facts";
import { Notice } from "../../components/Notice";
import { describeError } from "../../lib/api";
import { formatDuration, relativeTime, STEM_LABELS, WARNING_TITLES } from "../../lib/format";
import { navigate } from "../../lib/router";
import { getRecent } from "../../lib/storage";
import { useJob } from "../../lib/useJob";
import { draftFromRequest, saveDraft } from "../create/draft";
import { ProgressPanel } from "./ProgressPanel";
import { StemList } from "./StemList";
import { Timeline } from "./Timeline";

export function JobPage({ id }: { id: string }) {
  const { job, manifest, error } = useJob(id);
  const recent = getRecent().find((r) => r.id === id);
  const prompt = manifest?.request.prompt ?? recent?.prompt;

  if (!job) {
    return error ? (
      <div className="empty" role="alert">
        <h1>We couldn't load this track</h1>
        <p>{describeError(error)}</p>
        <a className="btn btn--secondary" href="#/">Make a new track</a>
      </div>
    ) : (
      <div className="empty" aria-busy="true"><span className="spinner" aria-hidden="true" /> Loading…</div>
    );
  }

  const editAndRetry = () => {
    if (manifest) saveDraft(draftFromRequest(manifest.request));
    else if (recent) saveDraft({ ...draftFromRequest({ prompt: recent.prompt, duration_s: recent.duration_s }) });
    navigate("/");
  };

  return (
    <>
      <div className="page-head">
        <div className="row">
          <StatusBadge status={job.status} />
          <span className="muted">{relativeTime(job.created_at)}</span>
        </div>
        <h1>{prompt ? `“${prompt}”` : "Your track"}</h1>
        {job.kind === "regenerate" && job.parent_job_id && (
          <p>
            New version with a regenerated {STEM_LABELS[recent?.stem ?? ""]?.toLowerCase() ?? "stem"} part.{" "}
            <a href={`#/jobs/${job.parent_job_id}`}>Open the original</a>
          </p>
        )}
      </div>

      {(job.status === "queued" || job.status === "running") && (
        <div className="grid-2">
          <ProgressPanel job={job} />
          {job.warnings.length > 0 && <Notes job={job} />}
        </div>
      )}

      {job.status === "failed" && (
        <Card title="This track didn't finish">
          <div className="stack-sm">
            <Notice tone="danger" title={job.error?.code ?? "Error"}>{job.error?.message}</Notice>
            <p className="muted">
              {job.error?.retryable
                ? "This is usually temporary. Trying again often works."
                : "Changing the request should fix this."}
            </p>
            <div><Button variant="primary" onClick={editAndRetry}>Edit and try again</Button></div>
          </div>
        </Card>
      )}

      {job.status === "succeeded" && job.result && (
        <div className="grid-2">
          <div className="stack">
            <Card title="Full mix">
              <div className="stack">
                <AudioTrack hero title="Mix" subtitle={manifest ? `${formatDuration(manifest.duration_s)} · ${manifest.sample_rate / 1000} kHz WAV` : undefined}
                  src={job.result.mix_wav} downloadName="mix.wav" />
                {job.result.mix_ducked && (
                  <AudioTrack title="Mix under narration" subtitle="Music dips under speech" src={job.result.mix_ducked}
                    downloadName="mix_ducked.wav" />
                )}
                {manifest && <Timeline sections={manifest.sections} duration={manifest.duration_s} hit={manifest.hit_time_s} />}
              </div>
            </Card>
            <Card title="Stems" aside={<p>They add up exactly to the mix</p>}>
              <StemList job={job} manifest={manifest} />
            </Card>
          </div>
          <div className="stack">
            {manifest && (
              <Card title="About this track">
                <div className="stack">
                  <Facts items={[
                    ["Style", manifest.style.charAt(0).toUpperCase() + manifest.style.slice(1)],
                    ["Tempo", `${Math.round(manifest.tempo_bpm * 10) / 10} bpm`],
                    ["Key", manifest.key.name],
                    ["Length", formatDuration(manifest.duration_s)],
                    ["Loudness", `${signed(manifest.loudness.integrated_lufs)} LUFS`],
                    ["True peak", `${signed(manifest.loudness.true_peak_dbtp)} dBTP`],
                  ]} />
                  <p className="field__hint">
                    {manifest.qa.passed ? "Passed all checks" : "Checks flagged an issue"}: exact length, loudness,
                    peak, no clicks or gaps{manifest.loop.enabled ? ", seamless loop" : ", clean ending"}. Generated in{" "}
                    {manifest.timings_s.total.toFixed(1)} s.
                  </p>
                </div>
              </Card>
            )}
            {job.warnings.length > 0 && <Notes job={job} />}
            <Card title="Downloads">
              <div className="downloads">
                <a className="btn btn--secondary btn--sm" href={job.result.mix_wav} download="mix.wav">Mix (WAV)</a>
                {job.result.mix_mp3 && <a className="btn btn--secondary btn--sm" href={job.result.mix_mp3} download="mix.mp3">Mix (MP3)</a>}
                {job.result.mix_ducked && <a className="btn btn--secondary btn--sm" href={job.result.mix_ducked} download="mix_ducked.wav">Ducked mix</a>}
                <a className="btn btn--secondary btn--sm" href={job.result.manifest} download="music_manifest.json">Manifest (JSON)</a>
              </div>
              <p className="field__hint">Download links expire after a day. Reopen this page to refresh them.</p>
            </Card>
            <Button variant="ghost" onClick={editAndRetry}>Make a variation of this</Button>
          </div>
        </div>
      )}
    </>
  );
}

/** Typographic minus for negative dB values. */
const signed = (v: number) => v.toFixed(1).replace("-", "−");

function Notes({ job }: { job: { warnings: { code: string; message: string }[] } }) {
  return (
    <Card title="Notes">
      <div className="stack-sm">
        {job.warnings.map((w, i) => (
          <Notice key={w.code + i} tone="warn" title={WARNING_TITLES[w.code] ?? w.code}>{w.message}</Notice>
        ))}
      </div>
    </Card>
  );
}
