// Client for the Python FastAPI backend (../../api/main.py). In dev, relative
// /api paths are proxied by vite.config.ts -> http://127.0.0.1:8123. The
// production build (a standalone Node server, not behind that dev proxy)
// needs an absolute URL instead — set via VITE_API_BASE at build time (see
// .env.production); FastAPI's CORS config must allow that origin.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export type ApiJob = {
  id: string;
  source: "arbeitsagentur" | "arbeitnow" | "eures";
  title: string;
  company: string | null;
  location: string | null;
  remote: boolean;
  published: string | null;
  url: string | null;
  score: number | null;
  first_seen: string;
  description?: string;
  has_description?: boolean;
};

export type Stats = {
  total_jobs: number;
  scored_jobs: number;
  by_source: Record<string, number>;
};

export type Experience = {
  title: string | null;
  company: string | null;
  date_range: string | null;
  description: string;
};

export type Candidate = {
  id: string;
  name: string | null;
  source_file: string;
  skills: string[];
  roles: string[];
  experience: Experience[];
  education: string[];
  parsed_at: string;
};

export type Profile = {
  must_have: string[];
  nice_to_have: Record<string, number>;
  locations: string[];
  remote_bonus: number;
  alert_threshold: number;
  active_candidate_id: string | null;
  active_candidate_name: string | null;
};

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}) as { detail?: string });
    throw new ApiError(res.status, body.detail || res.statusText);
  }
  return res.json() as Promise<T>;
}

export { ApiError };

export type JobFilters = {
  q?: string | undefined;
  source?: string | undefined;
  remote?: boolean | undefined;
  minScore?: number | undefined;
  limit?: number | undefined;
};

export function getJobs(filters: JobFilters = {}): Promise<{ jobs: ApiJob[]; count: number }> {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.source) params.set("source", filters.source);
  if (filters.remote !== undefined) params.set("remote", String(filters.remote));
  if (filters.minScore !== undefined) params.set("min_score", String(filters.minScore));
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));
  return request(`/api/jobs?${params}`);
}

export function getJob(id: string): Promise<ApiJob> {
  return request(`/api/jobs/${id}`);
}

export function getStats(): Promise<Stats> {
  return request("/api/stats");
}

export function getCandidate(): Promise<Candidate> {
  return request("/api/candidate");
}

export function getProfile(): Promise<Profile> {
  return request("/api/profile");
}

export async function uploadCv(file: File): Promise<Candidate> {
  const form = new FormData();
  form.append("file", file);
  return request("/api/cv", { method: "POST", body: form });
}
