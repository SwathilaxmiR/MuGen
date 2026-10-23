import { useEffect, useState } from "react";
import { Card } from "../components/Card";
import { formatDuration, relativeTime, STEM_LABELS } from "../lib/format";
import { getRecent, type RecentJob } from "../lib/storage";

export function LibraryPage() {
  const [items, setItems] = useState<RecentJob[]>(getRecent);
  useEffect(() => {
    const on = () => setItems(getRecent());
    window.addEventListener("score:recent", on);
    return () => window.removeEventListener("score:recent", on);
  }, []);
  return (
    <>
      <div className="page-head">
        <span className="eyebrow">Library</span>
        <h1>Your recent tracks</h1>
        <p>Tracks started from this browser. Open one to listen, download or regenerate a part.</p>
      </div>
      <Card>
        {items.length === 0 ? (
          <div className="empty">
            <p>Nothing here yet.</p>
            <a className="btn btn--primary" href="#/">Make your first track</a>
          </div>
        ) : (
          <ul className="list">
            {items.map((j) => (
              <li key={j.id}>
                <a href={`#/jobs/${j.id}`}>
                  <span className="list__title">
                    {j.prompt}
                    {j.stem && <span className="muted"> · new {STEM_LABELS[j.stem]?.toLowerCase()}</span>}
                  </span>
                  <span className="muted list__meta">
                    {j.duration_s ? formatDuration(j.duration_s) + " · " : ""}{relativeTime(j.created)}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
