import type { RecommendedDestination, RunResponse } from "../types/api";

export type RunOptions = {
  skip_enrichment?: boolean;
};

export type CreateRunRequest = {
  constraints: Record<string, any>;
  options?: RunOptions;
};

const getBaseUrl = () => {
  if (typeof window !== "undefined") return "";
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  return "http://localhost:8000";
};

const getDirectUrl = () => {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
};

async function apiFetch(path: string, init?: RequestInit) {
  const baseUrl = getBaseUrl();
  const url = path.startsWith("http") ? path : `${baseUrl}${path}`;

  const res = await fetch(url, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res;
}

export type RecommendRequest = {
  origin: string;
  departing_date: string;
  returning_date?: string | null;
  vibe: string;
  budget: string;
  climate: string;
};

export async function recommendDestination(body: RecommendRequest): Promise<RecommendedDestination> {
  const res = await apiFetch(`${getDirectUrl()}/recommend`, { method: "POST", body: JSON.stringify(body) });
  return await res.json();
}

export async function createRun(body: CreateRunRequest): Promise<{ runId: string }> {
  const res = await apiFetch("/runs", { method: "POST", body: JSON.stringify(body) });
  return await res.json();
}

export async function getRun(runId: string): Promise<RunResponse> {
  const res = await apiFetch(`/runs/${runId}`, { method: "GET" });
  return await res.json();
}

export async function cancelRun(runId: string): Promise<void> {
  try {
    await apiFetch(`/runs/${runId}/cancel`, { method: "POST" });
  } catch {
  }
}

export function getExportUrl(runId: string, format: "pdf" | "xlsx"): string {
  return `/runs/${runId}/export/${format}`;
}
