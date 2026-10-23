import { Button } from "../../components/Button";
import { newKey } from "../../lib/format";
import type { SectionDraft } from "./draft";

interface Props {
  sections: SectionDraft[];
  duration: number;
  error?: string;
  onChange: (s: SectionDraft[]) => void;
}

const SUGGESTIONS = ["calm intro", "build", "uplifting peak", "tense", "outro"];

export function SectionsEditor({ sections, duration, error, onChange }: Props) {
  const update = (i: number, patch: Partial<SectionDraft>) =>
    onChange(sections.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const add = () => {
    const last = sections.length ? Number(sections[sections.length - 1].start) || 0 : -1;
    const start = sections.length ? Math.min(duration - 2, Math.round(last + duration / 4)) : 0;
    onChange([...sections, { key: newKey(), start: String(Math.max(0, start)), mood: SUGGESTIONS[sections.length % 5] }]);
  };
  return (
    <fieldset className="stack-sm fieldset">
      <legend className="field__label">
        Sections <span className="optional">(optional)</span>
      </legend>
      <p className="field__hint">
        Change the mood at set times. Each change lands on the nearest beat. Leave empty for an automatic
        intro → build → peak.
      </p>
      {sections.map((s, i) => (
        <div className="section-row" key={s.key}>
          <div className="field">
            <label className="field__hint" htmlFor={`sec-start-${s.key}`}>Starts at (s)</label>
            <input id={`sec-start-${s.key}`} className="input" type="number" min={0} max={duration} step="0.1"
              inputMode="decimal" value={s.start} onChange={(e) => update(i, { start: e.target.value })} />
          </div>
          <div className="field">
            <label className="field__hint" htmlFor={`sec-mood-${s.key}`}>Mood</label>
            <input id={`sec-mood-${s.key}`} className="input" value={s.mood} maxLength={200}
              onChange={(e) => update(i, { mood: e.target.value })} />
          </div>
          <Button variant="ghost" size="sm" onClick={() => onChange(sections.filter((_, j) => j !== i))}
            aria-label={`Remove section ${i + 1}`}>
            Remove
          </Button>
        </div>
      ))}
      {error && <p className="field__error" role="alert">{error}</p>}
      <div>
        <Button size="sm" onClick={add} disabled={sections.length >= 32}>+ Add section</Button>
      </div>
    </fieldset>
  );
}
