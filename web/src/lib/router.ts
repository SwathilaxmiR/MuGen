import { useEffect, useState } from "react";

export type Route = { name: "create" } | { name: "job"; id: string } | { name: "library" };

export function parseHash(hash: string): Route {
  const m = hash.match(/^#\/jobs\/([0-9a-f-]{36})$/i);
  if (m) return { name: "job", id: m[1] };
  if (hash === "#/library") return { name: "library" };
  return { name: "create" };
}

export function navigate(to: string) {
  window.location.hash = to;
}

/** Minimal hash router: no dependency, works from any static file server. */
export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}
