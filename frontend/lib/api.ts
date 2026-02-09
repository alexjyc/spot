import type { RunResponse } from "../types/api";

export type RunOptions = {
  skip_enrichment?: boolean;
};

export type CreateRunRequest = {
  constraints: Record<string, any>;
  options?: RunOptions;
};

const getBaseUrl = () => {
  if (typeof window !== "undefined") return ""; // Browser: use relative path (proxy)
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  return "http://localhost:8000"; // Fallback for SSG/SSR
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

export async function createRun(body: CreateRunRequest): Promise<{ runId: string }> {
  const res = await apiFetch("/api/runs", { method: "POST", body: JSON.stringify(body) });
  return await res.json();
}

export async function getRun(runId: string): Promise<RunResponse> {
  const res = await apiFetch(`/api/runs/${runId}`, { method: "GET" });
  return await res.json();
}

export async function cancelRun(runId: string): Promise<void> {
  try {
    await apiFetch(`/api/runs/${runId}/cancel`, { method: "POST" });
  } catch {
    /* best-effort */
  }
}

export function getExportUrl(runId: string, format: "pdf" | "xlsx"): string {
  return `/api/runs/${runId}/export/${format}`;
}
