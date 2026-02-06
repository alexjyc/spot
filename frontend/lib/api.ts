export type RunOptions = {
  country?: string;
  days?: number;
  pace?: "relaxed" | "standard" | "packed";
  budget?: number;
  interests?: string[];
  avoid?: string[];
  must_do?: string[];
  special_instructions?: string;
};

export type CreateRunRequest = {
  prompt: string;
  constraints?: Record<string, any>;
  options?: RunOptions;
};

async function apiFetch(path: string, init?: RequestInit) {
  const res = await fetch(path, {
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

export async function getRun(runId: string): Promise<any> {
  const res = await apiFetch(`/api/runs/${runId}`, { method: "GET" });
  return await res.json();
}

