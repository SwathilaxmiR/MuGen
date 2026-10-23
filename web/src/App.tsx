import { useEffect, useRef } from "react";
import { Header } from "./components/Header";
import { CreatePage } from "./features/create/CreatePage";
import { JobPage } from "./features/job/JobPage";
import { LibraryPage } from "./features/LibraryPage";
import { useRoute } from "./lib/router";

const TITLES = { create: "New track", job: "Track", library: "Library" };

export function App() {
  const route = useRoute();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);

  // On navigation: update the title and move focus to the content, so screen readers announce the new page.
  useEffect(() => {
    document.title = `${TITLES[route.name]} · Score`;
    if (first.current) {
      first.current = false;
      return;
    }
    main.current?.focus();
    window.scrollTo({ top: 0 });
  }, [route]);

  return (
    <div className="shell">
      <a className="skip-link" href="#main" onClick={(e) => { e.preventDefault(); main.current?.focus(); }}>
        Skip to content
      </a>
      <Header route={route} />
      <main className="main" id="main" ref={main} tabIndex={-1}>
        {route.name === "job" ? <JobPage key={route.id} id={route.id} /> : route.name === "library" ? <LibraryPage /> : <CreatePage />}
      </main>
      <footer className="footer">
        <span>Instrumental, AI-generated music. Every manifest labels it so.</span>
        <a href="/docs">API docs</a>
      </footer>
    </div>
  );
}
