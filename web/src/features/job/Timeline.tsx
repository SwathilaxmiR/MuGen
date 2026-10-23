import type { ManifestSection } from "../../lib/types";

// intensity 0..4 -> a quiet-to-strong tint of the accent colour
const TINT = [8, 14, 24, 36, 50];

export function Timeline({ sections, duration, hit }: { sections: ManifestSection[]; duration: number; hit: number | null }) {
  const end = hit ?? duration;
  return (
    <figure className="timeline" aria-label="Section timeline">
      <div className="timeline__bar">
        {sections.map((s, i) => {
          const next = sections[i + 1]?.applied_start_s ?? end;
          const width = ((next - s.applied_start_s) / duration) * 100;
          return (
            <div key={i} className="timeline__seg"
              style={{ width: `${width}%`, background: `color-mix(in srgb, var(--accent) ${TINT[s.intensity] ?? 24}%, var(--surface))` }}
              title={`${s.mood} at ${s.applied_start_s.toFixed(2)} s`}>
              {s.mood}
            </div>
          );
        })}
        {hit !== null && <div className="timeline__seg timeline__seg--tail" style={{ width: `${((duration - end) / duration) * 100}%` }} aria-hidden="true" />}
      </div>
      <figcaption className="timeline__axis">
        <span>0 s</span>
        <span>{hit !== null ? `final hit ${hit.toFixed(1)} s · ` : "loops · "}{duration} s</span>
      </figcaption>
      <ul className="sr-only">
        {sections.map((s, i) => (
          <li key={i}>{s.mood} starts at {s.applied_start_s.toFixed(2)} seconds, intensity {s.intensity} of 4</li>
        ))}
      </ul>
    </figure>
  );
}
