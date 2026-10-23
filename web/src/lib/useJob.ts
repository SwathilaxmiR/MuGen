import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { JobStatus, Manifest } from "./types";

/** Polls a job until it finishes (1 s, easing to 3 s), then loads its manifest once. */
export function useJob(id: string) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [error, setError] = useState<unknown>(null);
  const timer = useRef<number>();

  useEffect(() => {
    let alive = true;
    let delay = 1000;
    setJob(null);
    setManifest(null);
    setError(null);

    const tick = async () => {
      try {
        const j = await api.job(id);
        if (!alive) return;
        setJob(j);
        setError(null);
        if (j.status === "succeeded") {
          const m = await api.manifest(id);
          if (alive) setManifest(m);
          return;
        }
        if (j.status === "failed") return;
      } catch (e) {
        if (!alive) return;
        setError(e);
        if (e instanceof ApiError && !e.retryable) return;
      }
      delay = Math.min(3000, delay * 1.25);
      timer.current = window.setTimeout(tick, delay);
    };
    tick();
    return () => {
      alive = false;
      window.clearTimeout(timer.current);
    };
  }, [id]);

  return { job, manifest, error };
}
