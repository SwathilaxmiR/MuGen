import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Field } from "../../components/Field";
import { Notice } from "../../components/Notice";
import { api, describeError } from "../../lib/api";
import { formatDuration, newKey } from "../../lib/format";
import { navigate } from "../../lib/router";
import { addRecent } from "../../lib/storage";
import { EMPTY_DRAFT, loadDraft, saveDraft, toRequest, validate, type Draft, type Errors } from "./draft";
import { SectionsEditor } from "./SectionsEditor";

const EXAMPLES = [
  "Calm cinematic piano that builds to an uplifting peak",
  "Chill lo-fi beats for studying late at night",
  "Upbeat corporate background for a product video",
  "Tense, dark thriller underscore",
  "Playful, quirky music for a kids' cartoon",
  "Smooth jazz lounge with saxophone",
];
const LENGTHS = [15, 30, 60, 120];
const TONICS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];

export function CreatePage() {
  const [d, setD] = useState<Draft>(loadDraft);
  const [errors, setErrors] = useState<Errors>({});
  const [narration, setNarration] = useState<File | null>(null);
  const [busy, setBusy] = useState<"" | "upload" | "submit">("");
  const [apiError, setApiError] = useState("");
  const idemKey = useRef(newKey()); // one key per attempt: a double click can't create two jobs
  const promptRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => saveDraft(d), [d]);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => {
    setD((prev) => ({ ...prev, [k]: v }));
    idemKey.current = newKey();
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const errs = validate(d);
    setErrors(errs);
    setApiError("");
    if (Object.keys(errs).length) {
      if (errs.prompt) promptRef.current?.focus();
      return;
    }
    try {
      let narrationUrl: string | undefined;
      if (narration) {
        setBusy("upload");
        narrationUrl = (await api.upload(narration)).url;
      }
      setBusy("submit");
      const req = toRequest(d, narrationUrl);
      const res = await api.createJob(req, idemKey.current);
      addRecent({ id: res.job_id, prompt: req.prompt, duration_s: req.duration_s, created: new Date().toISOString() });
      navigate(`/jobs/${res.job_id}`);
    } catch (err) {
      setApiError(describeError(err));
      setBusy("");
    }
  }

  const advancedCount = [d.tempo, d.key, d.seed].filter(Boolean).length + (d.loopable ? 1 : 0) +
    (d.lufs !== -16 ? 1 : 0) + (d.sampleRate !== 48000 ? 1 : 0);

  return (
    <>
      <div className="page-head">
        <span className="eyebrow">New track</span>
        <h1>Describe the music. Get a finished track and its stems.</h1>
        <p>Instrumental background music at the exact length you need, mastered to a standard loudness, with
          drums, bass, harmony and melody as separate files.</p>
      </div>

      <form onSubmit={onSubmit} noValidate className="grid-2">
        <div className="stack">
          <Card title="What should it sound like?">
            <div className="stack">
              <Field label="Description" error={errors.prompt}
                hint="Mood, genre, energy, instruments. Song and artist names are ignored, and vocals aren't supported.">
                <textarea ref={promptRef} className="textarea" value={d.prompt} maxLength={2000} required
                  placeholder="e.g. warm acoustic guitar for a travel vlog, gentle and optimistic"
                  onChange={(e) => set("prompt", e.target.value)} />
              </Field>
              <div className="stack-sm">
                <span className="field__hint" id="examples-label">Or start from an example</span>
                <div className="chips" role="group" aria-labelledby="examples-label">
                  {EXAMPLES.map((x) => (
                    <button type="button" key={x} className="chip" aria-pressed={d.prompt === x}
                      onClick={() => set("prompt", x)}>{x}</button>
                  ))}
                </div>
              </div>
            </div>
          </Card>

          <Card title="Structure">
            <div className="stack">
              <div className="field">
                <label className="field__label" htmlFor="duration">Length</label>
                <div className="range-row">
                  <input type="range" min={5} max={300} step={1} value={d.duration} aria-label="Length in seconds"
                    aria-valuetext={formatDuration(d.duration)} onChange={(e) => set("duration", Number(e.target.value))} />
                  <input id="duration" className="input" type="number" min={5} max={300} step="0.1" inputMode="decimal"
                    value={d.duration} aria-describedby="duration-hint" aria-invalid={errors.duration ? true : undefined}
                    onChange={(e) => set("duration", Number(e.target.value))} />
                </div>
                <p className="field__hint" id="duration-hint">
                  {formatDuration(d.duration)}. Every file is exactly this long and ends on a musical bar line.
                </p>
                {errors.duration && <p className="field__error" role="alert">{errors.duration}</p>}
                <div className="chips" role="group" aria-label="Common lengths">
                  {LENGTHS.map((l) => (
                    <button type="button" key={l} className="chip" aria-pressed={d.duration === l}
                      onClick={() => set("duration", l)}>{formatDuration(l)}</button>
                  ))}
                </div>
              </div>
              <SectionsEditor sections={d.sections} duration={d.duration} error={errors.sections}
                onChange={(s) => set("sections", s)} />
            </div>
          </Card>
        </div>

        <div className="stack">
          <Card title="Voice-over">
            <div className="stack-sm">
              <p className="field__hint">Add narration and you also get a version where the music dips about 12 dB
                under speech.</p>
              <div className="file-drop">
                <span className="muted" aria-live="polite">{narration ? narration.name : "No file selected"}</span>
                <div className="row">
                  {narration && <Button variant="ghost" size="sm" onClick={() => setNarration(null)}>Remove</Button>}
                  <label className="btn btn--secondary btn--sm">
                    {narration ? "Replace" : "Choose audio"}
                    <input type="file" accept="audio/*" className="sr-only"
                      onChange={(e) => setNarration(e.target.files?.[0] ?? null)} />
                  </label>
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <details className="disclosure disclosure--flush">
              <summary>
                <span>Fine-tune</span>
                <span>{advancedCount ? `${advancedCount} set` : "Automatic"}</span>
              </summary>
              <div className="disclosure__body">
                <div className="fields-3">
                  <Field label="Tempo (bpm)" optional error={errors.tempo}>
                    <input className="input" type="number" min={40} max={200} inputMode="numeric" placeholder="Auto"
                      value={d.tempo} onChange={(e) => set("tempo", e.target.value)} />
                  </Field>
                  <Field label="Key" optional>
                    <select className="select" value={d.key} onChange={(e) => set("key", e.target.value)}>
                      <option value="">Auto</option>
                      {["major", "minor"].map((m) => (
                        <optgroup key={m} label={m === "major" ? "Major" : "Minor"}>
                          {TONICS.map((t) => <option key={t + m} value={`${t} ${m}`}>{t} {m}</option>)}
                        </optgroup>
                      ))}
                    </select>
                  </Field>
                  <Field label="Seed" optional error={errors.seed} hint="Same seed + settings = same music.">
                    <input className="input" inputMode="numeric" placeholder="Random" value={d.seed}
                      onChange={(e) => set("seed", e.target.value.trim())} />
                  </Field>
                </div>
                <div className="fields-3">
                  <Field label="Loudness">
                    <select className="select" value={d.lufs} onChange={(e) => set("lufs", Number(e.target.value))}>
                      <option value={-14}>−14 LUFS · streaming</option>
                      <option value={-16}>−16 LUFS · web video (default)</option>
                      <option value={-23}>−23 LUFS · broadcast</option>
                    </select>
                  </Field>
                  <Field label="Sample rate">
                    <select className="select" value={d.sampleRate}
                      onChange={(e) => set("sampleRate", Number(e.target.value) as 44100 | 48000)}>
                      <option value={48000}>48 kHz (video)</option>
                      <option value={44100}>44.1 kHz (music)</option>
                    </select>
                  </Field>
                </div>
                <label className="check">
                  <input type="checkbox" checked={d.loopable} onChange={(e) => set("loopable", e.target.checked)} />
                  <span>Seamless loop<small>Ends exactly where it starts, with no final hit. The tempo may shift slightly to fit.</small></span>
                </label>
                <label className="check">
                  <input type="checkbox" checked={d.mp3} onChange={(e) => set("mp3", e.target.checked)} />
                  <span>Also make an MP3<small>The WAV is always included.</small></span>
                </label>
              </div>
            </details>
          </Card>

          <div className="stack-sm">
            {apiError && <Notice tone="danger" title="Couldn't start the track">{apiError}</Notice>}
            <Button variant="primary" type="submit" block loading={!!busy}>
              {busy === "upload" ? "Uploading narration…" : busy === "submit" ? "Starting…" : "Generate music"}
            </Button>
            <div className="row row--between">
              <span className="field__hint">Usually ready in under a minute.</span>
              {(d.prompt || d.sections.length > 0) && (
                <Button variant="ghost" size="sm" onClick={() => { setD(EMPTY_DRAFT); setErrors({}); setNarration(null); }}>
                  Clear form
                </Button>
              )}
            </div>
          </div>
        </div>
      </form>
    </>
  );
}
