// Per-browser conveniences only: the access token and a list of recent job ids.
const TOKEN = "score.token";
const RECENT = "score.recent";

function safe<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    return fallback;
  }
}

export const getToken = () => safe(() => localStorage.getItem(TOKEN) ?? "", "");
export const setToken = (t: string) =>
  safe(() => (t ? localStorage.setItem(TOKEN, t) : localStorage.removeItem(TOKEN)), undefined);

export interface RecentJob {
  id: string;
  prompt: string;
  duration_s: number;
  created: string;
  parent?: string;
  stem?: string;
}

export const getRecent = (): RecentJob[] => safe(() => JSON.parse(localStorage.getItem(RECENT) ?? "[]"), []);

export function addRecent(job: RecentJob) {
  const list = [job, ...getRecent().filter((j) => j.id !== job.id)].slice(0, 20);
  safe(() => localStorage.setItem(RECENT, JSON.stringify(list)), undefined);
  window.dispatchEvent(new Event("score:recent"));
}
