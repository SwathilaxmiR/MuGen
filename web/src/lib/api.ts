import type { JobStatus, Manifest, MusicRequest } from "./types";
import { getToken } from "./storage";

/** Error carrying the API's JSON error body ({error: {code, message, retryable}}). */
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public retryable = false,
  ) {
    super(message);
  }
}

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(BASE + path, { ...init, headers });
  } catch {
    throw new ApiError("NETWORK", "Cannot reach the music engine. Is the API running?", 0, true);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const e = body?.error;
    throw new ApiError(e?.code ?? "HTTP_" + res.status, e?.message ?? res.statusText, res.status, !!e?.retryable);
  }
  return body as T;
}

export const api = {
  createJob: (req: MusicRequest, idempotencyKey: string) =>
    request<{ job_id: string; status: string; status_url: string }>("/api/v1/music/jobs", {
      method: "POST",
      body: JSON.stringify(req),
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  job: (id: string) => request<JobStatus>(`/api/v1/jobs/${encodeURIComponent(id)}`),
  manifest: (id: string) => request<Manifest>(`/api/v1/jobs/${encodeURIComponent(id)}/manifest`),
  regenerate: (id: string, stem: string, idempotencyKey: string) =>
    request<{ job_id: string }>(`/api/v1/music/jobs/${encodeURIComponent(id)}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ stem }),
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ url: string; size_bytes: number }>("/api/v1/uploads", { method: "POST", body: form });
  },
  ready: () => request<{ status: string; checks: Record<string, string> }>("/ready"),
};

/** Friendly copy for the error codes in README.md. */
export function describeError(e: unknown): string {
  if (!(e instanceof ApiError)) return "Something went wrong. Please try again.";
  switch (e.code) {
    case "UNAUTHORIZED":
      return "This server needs an access token. Add it under Settings.";
    case "RATE_LIMITED":
      return "Too many requests in a minute. Wait a moment and try again.";
    case "QUEUE_FULL":
      return "The queue is full right now. Try again shortly.";
    case "JOB_NOT_FOUND":
      return "That job doesn't exist (or was created on another server).";
    default:
      return e.message;
  }
}
