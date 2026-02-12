import type { NodeEventPayload, ArtifactEventPayload, LogEventPayload } from "../types/api";

type Handlers = {
  onNode: (data: NodeEventPayload) => void;
  onArtifact: (data: ArtifactEventPayload) => void;
  onLog: (data: LogEventPayload) => void;
  onError: (err: unknown) => void;
};

function buildSseUrl(runId: string): string {
  const rawBase = (process.env.NEXT_PUBLIC_API_URL || "").trim();
  const base = rawBase || "http://127.0.0.1:8000";
  const normalizedBase = base.replace(/\/+$/, "");
  return `${normalizedBase}/runs/${encodeURIComponent(runId)}/events`;
}

export function subscribeToRunEvents(runId: string, handlers: Handlers) {
  const es = new EventSource(buildSseUrl(runId));

  let firstEventTimer: ReturnType<typeof setTimeout> | null = setTimeout(() => {
    firstEventTimer = null;
    es.close();
    handlers.onError("SSE timeout: no events received");
  }, 2_500);

  const clearFirstEventTimer = () => {
    if (firstEventTimer !== null) {
      clearTimeout(firstEventTimer);
      firstEventTimer = null;
    }
  };

  es.addEventListener("node", (ev) => {
    clearFirstEventTimer();
    try {
      handlers.onNode(JSON.parse((ev as MessageEvent).data));
    } catch (e) {
      handlers.onError(e);
    }
  });
  es.addEventListener("artifact", (ev) => {
    clearFirstEventTimer();
    try {
      handlers.onArtifact(JSON.parse((ev as MessageEvent).data));
    } catch (e) {
      handlers.onError(e);
    }
  });
  es.addEventListener("log", (ev) => {
    clearFirstEventTimer();
    try {
      handlers.onLog(JSON.parse((ev as MessageEvent).data));
    } catch { }
  });
  es.onerror = () => {
    clearFirstEventTimer();
    handlers.onError("Connection error");
  };

  return {
    close() {
      clearFirstEventTimer();
      es.close();
    },
  };
}
