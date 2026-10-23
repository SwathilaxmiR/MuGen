import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: ReactNode;
  src: string;
  downloadName: string;
  hero?: boolean;
  actions?: ReactNode;
}

/** One playable file: native controls (keyboard + screen-reader friendly) plus a download link. */
export function AudioTrack({ title, subtitle, src, downloadName, hero, actions }: Props) {
  return (
    <div className={`track ${hero ? "track--hero" : ""}`}>
      <div className="track__head">
        <div className="track__title">
          <h3>{title}</h3>
          {subtitle && <small>{subtitle}</small>}
        </div>
        <div className="row">
          {actions}
          <a className="btn btn--ghost btn--sm" href={src} download={downloadName}>
            Download<span className="sr-only"> {title}</span>
          </a>
        </div>
      </div>
      <audio controls preload="metadata" src={src} aria-label={`${title} player`} />
    </div>
  );
}
