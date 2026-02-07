import type { NodeEventPayload, ArtifactEventPayload, LogEventPayload } from "../types/api";

type Handlers = {
  onNode: (data: NodeEventPayload) => void;
  onArtifact: (data: ArtifactEventPayload) => void;
  onLog: (data: LogEventPayload) => void;
  onError: (err: unknown) => void;
};

export function subscribeToRunEvents(runId: string, handlers: Handlers) {
  const es = new EventSource(`/api/runs/${runId}/events`);

  es.addEventListener("node", (ev) => {
    try {
      handlers.onNode(JSON.parse((ev as MessageEvent).data));
    } catch (e) {
      handlers.onError(e);
    }
  });
  es.addEventListener("artifact", (ev) => {
    try {
      handlers.onArtifact(JSON.parse((ev as MessageEvent).data));
    } catch (e) {
      handlers.onError(e);
    }
  });
  es.addEventListener("log", (ev) => {
    try {
      handlers.onLog(JSON.parse((ev as MessageEvent).data));
    } catch { }
  });
  es.onerror = () => handlers.onError("Connection error");

  return {
    close() {
      es.close();
    },
  };
}
