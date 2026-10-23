import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Route } from "../lib/router";
import { SettingsDialog } from "./SettingsDialog";

export function Header({ route }: { route: Route }) {
  const [settings, setSettings] = useState(false);
  const [ready, setReady] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    const check = () => api.ready().then(() => alive && setReady(true), () => alive && setReady(false));
    check();
    const t = window.setInterval(check, 30000);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, []);

  const current = (name: Route["name"]) => (route.name === name ? "page" : undefined);
  const statusText = ready === null ? "Checking server" : ready ? "Server ready" : "Server unavailable";
  return (
    <header className="header">
      <div className="header__inner">
        <a className="brand" href="#/" aria-label="Score, home">
          <span className="brand__mark" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 32 32" fill="none">
              <path d="M5 20v-8M11 25V7M17 20v-8M23 17v-2M29 19v-6" stroke="white" strokeWidth="3" strokeLinecap="round" />
            </svg>
          </span>
          <span className="brand__name">Score</span>
        </a>
        <nav className="nav" aria-label="Main">
          <a href="#/" aria-current={current("create")}>New track</a>
          <a href="#/library" aria-current={current("library")}>Library</a>
        </nav>
        <span className={`status-dot ${ready === null ? "" : ready ? "status-dot--ok" : "status-dot--down"}`}
          role="img" aria-label={statusText} title={statusText} />
        <button className="icon-btn" onClick={() => setSettings(true)} aria-label="Settings">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d="M4 7h10M18 7h2M4 17h4M12 17h8" strokeLinecap="round" />
            <circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" />
          </svg>
        </button>
      </div>
      <SettingsDialog open={settings} onClose={() => setSettings(false)} />
    </header>
  );
}
