"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { format, isBefore, startOfDay } from "date-fns";
import { Search, MapPin, Target } from "lucide-react";
import { motion } from "framer-motion";
import ResultsView from "../components/ResultsView";
import { createRun, getRun, cancelRun, recommendDestination } from "../lib/api";
import { subscribeToRunEvents } from "../lib/sse";
import { DatePicker } from "../components/ui/DatePicker";
import type { SpotOnResults, NodeEventPayload, ArtifactEventPayload, RecommendedDestination } from "../types/api";

export default function Page() {
  const [origin, setOrigin] = useState("");
  const [departingDate, setDepartingDate] = useState<Date | undefined>(undefined);
  const [returningDate, setReturningDate] = useState<Date | undefined>(undefined);
  const [vibe, setVibe] = useState("");
  const [budget, setBudget] = useState("");
  const [climate, setClimate] = useState("");
  const [recommendation, setRecommendation] = useState<RecommendedDestination | null>(null);
  const [recommending, setRecommending] = useState(false);
  const [results, setResults] = useState<SpotOnResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<Record<string, NodeEventPayload>>({});
  const [logs, setLogs] = useState<string[]>([]);
  const [enrichmentEnabled, setEnrichmentEnabled] = useState(false);
  const [backendHealth, setBackendHealth] = useState<{
    status: "unknown" | "ok" | "down";
    latencyMs?: number;
    lastCheckedAt?: number;
  }>({ status: "unknown" });

  const eventSourceRef = useRef<{ close: () => void } | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const pollIntervalRef = useRef<number | null>(null);
  const runIdRef = useRef<string | null>(null);

  const cleanup = (cancel = false) => {
    if (cancel && runIdRef.current) {
      cancelRun(runIdRef.current);
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (pollIntervalRef.current) {
      window.clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  useEffect(() => {
    const handleBeforeUnload = () => {
      if (runIdRef.current) {
        navigator.sendBeacon(`/runs/${runIdRef.current}/cancel`);
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("pagehide", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("pagehide", handleBeforeUnload);
      cleanup(false);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      const t0 = performance.now();
      try {
        const res = await fetch("/health", { cache: "no-store" });
        const json = await res.json().catch(() => null);
        const ok = res.ok && !!json && (json as any).ok === true;
        if (cancelled) return;
        setBackendHealth({
          status: ok ? "ok" : "down",
          latencyMs: Math.round(performance.now() - t0),
          lastCheckedAt: Date.now(),
        });
      } catch {
        if (cancelled) return;
        setBackendHealth({
          status: "down",
          latencyMs: Math.round(performance.now() - t0),
          lastCheckedAt: Date.now(),
        });
      }
    };

    check();
    const id = window.setInterval(check, 15_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const [fieldErrors, setFieldErrors] = useState<{ origin?: boolean; departing?: boolean; vibe?: boolean; budget?: boolean; climate?: boolean }>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    cleanup(true);

    setError(null);
    setFieldErrors({});

    const newErrors = {
      origin: !origin.trim(),
      departing: !departingDate,
      vibe: !vibe,
      budget: !budget,
      climate: !climate,
    };

    if (departingDate && returningDate && isBefore(returningDate, departingDate)) {
      setFieldErrors(prev => ({ ...prev, departing: true }));
      setError("Return date must be after departing date");
      return;
    }

    if (Object.values(newErrors).some(Boolean)) {
      setFieldErrors(newErrors);
      return;
    }

    setLoading(true);
    setRecommending(true);
    setRecommendation(null);
    setResults(null);
    setRunId(null);
    setNodes({});
    setLogs([]);

    const deptStr = format(departingDate!, "yyyy-MM-dd");
    const retStr = returningDate ? format(returningDate, "yyyy-MM-dd") : "";

    let recommended: RecommendedDestination;
    try {
      setNodes({ RecommendDestination: { node: "RecommendDestination", status: "start", message: "Finding your destination..." } });
      recommended = await recommendDestination({
        origin,
        departing_date: deptStr,
        returning_date: retStr || undefined,
        vibe,
        budget,
        climate,
      });
      setRecommendation(recommended);
      setRecommending(false);
      setNodes(prev => ({ ...prev, RecommendDestination: { node: "RecommendDestination", status: "end", message: "Destination found" } }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to recommend destination");
      setLoading(false);
      setRecommending(false);
      return;
    }

    const constraints = {
      origin,
      destination: recommended.destination,
      departing_date: deptStr,
      returning_date: retStr || null,
    };

    try {
      const { runId } = await createRun({ constraints, options: { skip_enrichment: !enrichmentEnabled } });
      setRunId(runId);
      runIdRef.current = runId;
      setNodes((prev) => ({
        ...prev,
        Queue: { node: "Queue", status: "start", message: "Queued" },
      }));

      const startPollingFallback = () => {
        if (pollIntervalRef.current) return;
        pollIntervalRef.current = window.setInterval(async () => {
          try {
            const run = await getRun(runId);
            if (run?.progress?.nodes) {
              setNodes((prev) => ({ ...prev, ...run.progress!.nodes }));
            }
            if (run.status === "done") {
              setResults(run.final_output ?? null);
              setLoading(false);
              runIdRef.current = null;
              cleanup();
            } else if (run.status === "error") {
              setError(run.error?.message || "Run failed");
              setLoading(false);
              runIdRef.current = null;
              cleanup();
            } else if (run.status === "cancelled") {
              setError("Run was cancelled");
              setLoading(false);
              runIdRef.current = null;
              cleanup();
            }
          } catch {
          }
        }, 2000);
      };

      eventSourceRef.current = subscribeToRunEvents(runId, {
        onNode: (data: NodeEventPayload) => {
          if (data?.node) setNodes((prev) => ({ ...prev, [data.node]: data }));
        },
        onLog: (data: { message?: string }) => {
          const msg = data?.message;
          if (!msg) return;

          if (
            msg === "Run started" ||
            msg === "Run completed" ||
            msg === "Run failed" ||
            msg === "Run cancelled"
          ) {
            return;
          }
          setLogs((prev) => [...prev.slice(-30), msg]);
        },
        onArtifact: (data: ArtifactEventPayload) => {
          if (data?.type === "final_output" && data.payload?.final_output) {
            setResults(data.payload.final_output as SpotOnResults);
            setLoading(false);
            runIdRef.current = null;
            cleanup();
            return;
          }
          if (data?.type === "constraints" && data.payload?.constraints) {
            setResults((prev) => ({
              ...(prev || {}),
              constraints: data.payload.constraints as Record<string, unknown>,
            }));
          }
        },
        onError: () => {
          cleanup();
          startPollingFallback();
        },
      });

      timeoutRef.current = window.setTimeout(() => {
        setError("Request timed out");
        setLoading(false);
        cleanup();
      }, 300000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setLoading(false);
      cleanup();
    }
  };

  const orderedNodes = [
    "RecommendDestination",
    "Queue",
    "ParseRequest",
    "RestaurantAgent",
    "AttractionsAgent",
    "HotelAgent",
    "TransportAgent",
    ...(enrichmentEnabled ? ["EnrichAgent"] : []),
    "QualitySplit",
    "BudgetAgent",
  ];

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#ffffff",
        paddingBottom: "80px",
      }}
    >
      <div
        style={{
          background: "linear-gradient(180deg, #f7f7f7 0%, #ffffff 100%)",
          padding: "80px 20px 60px",
          textAlign: "center",
        }}
      >
        <div style={{ maxWidth: 800, margin: "0 auto" }}>

          <h1
            style={{
              fontSize: "clamp(48px, 5vw, 72px)",
              fontWeight: 800,
              color: "#1d1d1f",
              margin: 0,
              letterSpacing: "-0.04em",
              lineHeight: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "16px",
            }}
          >
            Spot On <Target size={56} color="#FF4F00" strokeWidth={2.5} />
          </h1>
          <p
            style={{
              fontSize: "21px",
              color: "#86868b",
              marginTop: "24px",
              fontWeight: 400,
              maxWidth: "540px",
              margin: "24px auto 0",
              lineHeight: 1.5,
              letterSpacing: "-0.01em",
            }}
          >
            AI-powered travel recommendations. <br />
            Simply curated. Beautifully presented.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 1000, margin: "-40px auto 0", padding: "0 20px", position: "relative", zIndex: 10 }}>
        <form
          onSubmit={handleSubmit}
          noValidate
          style={{
            background: "rgba(255, 255, 255, 0.9)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            padding: "32px",
            borderRadius: "32px",
            boxShadow: "0 20px 40px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04)",
            border: "1px solid rgba(255,255,255,0.4)",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: 24,
              marginBottom: 32,
            }}
          >
            <div style={fieldContainerStyle}>
              <label style={labelStyle}>Where from?</label>
              <TextInput
                placeholder="City or Airport"
                value={origin}
                onChange={(val) => {
                  setOrigin(val);
                  if (fieldErrors.origin)
                    setFieldErrors((prev) => ({ ...prev, origin: false }));
                }}
                hasError={fieldErrors.origin}
                icon={
                  <MapPin
                    size={18}
                    color={fieldErrors.origin ? "#ff3b30" : "#86868b"}
                  />
                }
              />
            </div>

            <div style={fieldContainerStyle}>
              <label style={labelStyle}>Departing</label>
              <DatePicker
                selected={departingDate}
                onSelect={(date) => {
                  setDepartingDate(date);
                  if (date && returningDate && isBefore(returningDate, date)) {
                    setReturningDate(undefined);
                  }
                  if (fieldErrors.departing) setFieldErrors(prev => ({ ...prev, departing: false }));
                  setError(null);
                }}
                hasError={fieldErrors.departing}
                placeholder="Add date"
                minDate={new Date(new Date().setHours(0, 0, 0, 0))}
              />
            </div>

            <div style={fieldContainerStyle}>
              <label style={labelStyle}>
                Return <span style={{ fontWeight: 400, color: "#86868b", textTransform: "none" }}>(optional)</span>
              </label>
              <DatePicker
                selected={returningDate}
                onSelect={(date) => {
                  if (departingDate && date && isBefore(date, departingDate)) return;
                  setReturningDate(date);
                }}
                placeholder="Add date"
                minDate={departingDate || startOfDay(new Date())}
              />
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 20, marginBottom: 32 }}>
            <div>
              <label style={labelStyle}>Trip Vibe</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 10 }}>
                {["Adventure", "Culture & History", "Beach & Relaxation", "Food & Nightlife"].map((option) => (
                  <PillButton
                    key={option}
                    label={option}
                    selected={vibe === option}
                    hasError={fieldErrors.vibe && !vibe}
                    onClick={() => {
                      setVibe(option);
                      if (fieldErrors.vibe) setFieldErrors(prev => ({ ...prev, vibe: false }));
                    }}
                  />
                ))}
              </div>
            </div>
            <div>
              <label style={labelStyle}>Budget</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 10 }}>
                {["Budget-friendly", "Mid-range", "Luxury"].map((option) => (
                  <PillButton
                    key={option}
                    label={option}
                    selected={budget === option}
                    hasError={fieldErrors.budget && !budget}
                    onClick={() => {
                      setBudget(option);
                      if (fieldErrors.budget) setFieldErrors(prev => ({ ...prev, budget: false }));
                    }}
                  />
                ))}
              </div>
            </div>
            <div>
              <label style={labelStyle}>Climate</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 10 }}>
                {["Warm", "Moderate", "Cold"].map((option) => (
                  <PillButton
                    key={option}
                    label={option}
                    selected={climate === option}
                    hasError={fieldErrors.climate && !climate}
                    onClick={() => {
                      setClimate(option);
                      if (fieldErrors.climate) setFieldErrors(prev => ({ ...prev, climate: false }));
                    }}
                  />
                ))}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                cursor: "pointer",
                userSelect: "none",
              }}
            >
              <div
                onClick={() => setEnrichmentEnabled((v) => !v)}
                style={{
                  width: 44,
                  height: 24,
                  borderRadius: 12,
                  background: enrichmentEnabled
                    ? "linear-gradient(135deg, #FF4F00 0%, #FF2E00 100%)"
                    : "#d2d2d7",
                  position: "relative",
                  transition: "background 0.2s ease",
                  flexShrink: 0,
                }}
              >
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    background: "#ffffff",
                    position: "absolute",
                    top: 2,
                    left: enrichmentEnabled ? 22 : 2,
                    transition: "left 0.2s ease",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                  }}
                />
              </div>
              <span
                style={{
                  fontSize: "14px",
                  fontWeight: 500,
                  color: "#86868b",
                }}
              >
                Deep Research{" "}
              </span>
            </label>
            <button type="submit" disabled={loading} style={buttonStyle(loading)}>
              {loading ? (
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Spinner />
                  <span>{recommending ? "Finding Destination..." : "Curating Trip"}</span>
                </div>
              ) : (
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Search size={20} strokeWidth={2.5} />
                  <span>Discover</span>
                </div>
              )}
            </button>
          </div>
        </form>
      </div>

      <div style={{ maxWidth: 1000, margin: "60px auto 0", padding: "0 20px" }}>
        {recommendation && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              padding: "24px 28px",
              background: "linear-gradient(135deg, #FFF8F0 0%, #FFFFFF 100%)",
              border: "1px solid #FFD6B0",
              borderRadius: "20px",
              marginBottom: 32,
              boxShadow: "0 4px 12px rgba(255,79,0,0.06)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <MapPin size={18} color="#FF4F00" />
              <span style={{ fontSize: "13px", fontWeight: 600, color: "#FF4F00", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Your Destination
              </span>
            </div>
            <div style={{ fontSize: "22px", fontWeight: 700, color: "#1d1d1f", marginBottom: 6 }}>
              {recommendation.destination}
            </div>
            <div style={{ fontSize: "15px", color: "#6e6e73", lineHeight: 1.5 }}>
              {recommendation.reasoning}
            </div>
          </motion.div>
        )}

        {loading && (
          <div style={{ animation: "fadeIn 0.5s ease-out" }}>
            <div style={{
              marginBottom: 24,
              fontSize: "14px",
              fontWeight: 600,
              color: "#86868b",
              textTransform: "uppercase",
              letterSpacing: "0.04em"
            }}>
              Progress
            </div>

            <div style={{ display: "grid", gap: 8 }}>
              {orderedNodes.map((name, i) => {
                const ev = nodes[name];
                const status = ev?.status;
                const isActive = status === "start";
                const isDone = status === "end";

                return (
                  <motion.div
                    key={name}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{
                      opacity: status ? 1 : 0.4,
                      x: 0,
                      scale: isActive ? 1.02 : 1,
                      backgroundColor: isDone ? "rgba(52, 199, 89, 0.05)" : "#ffffff",
                      borderColor: isActive ? "#FF4F00" : isDone ? "#34c759" : "#e5e5ea",
                      boxShadow: isActive ? "0 4px 12px rgba(255,79,0,0.1)" : "none",
                    }}
                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "16px 20px",
                      borderWidth: "1px",
                      borderStyle: "solid",
                      borderRadius: "16px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <motion.div
                        animate={{
                          scale: isActive ? [1, 1.2, 1] : 1,
                          backgroundColor: isActive ? "#FF4F00" : isDone ? "#34c759" : ev?.status === "error" ? "#ff3b30" : "#d2d2d7"
                        }}
                        transition={isActive ? { repeat: Infinity, duration: 1.5 } : { duration: 0.3 }}
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                        }}
                      />
                      <span style={{ fontWeight: 600, fontSize: "15px" }}>{name}</span>
                    </div>
                    {isActive && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        style={{ fontSize: "13px", color: "#FF4F00", fontWeight: 500 }}
                      >
                        Thinking...
                      </motion.span>
                    )}
                    {isDone && (
                      <motion.span
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        style={{ fontSize: "13px", color: "#34c759", fontWeight: 600 }}
                      >
                        Completed
                      </motion.span>
                    )}
                  </motion.div>
                );
              })}
            </div>

            {logs.length > 0 && (
              <div style={{ marginTop: 32 }}>
                <div style={{
                  fontFamily: "ui-monospace, SFMono-Regular, monospace",
                  fontSize: 12,
                  background: "#1d1d1f",
                  color: "#f5f5f7",
                  borderRadius: 16,
                  padding: 20,
                  maxHeight: 200,
                  overflow: "auto",
                  lineHeight: 1.6
                }}>
                  {logs.map((l, idx) => (
                    <div key={`${idx}-${l}`} style={{ borderBottom: "1px solid #333", paddingBottom: 4, marginBottom: 4 }}>
                      {">"} {l}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {error && (
          <div
            style={{
              padding: "24px",
              background: "#fff0f0",
              border: "1px solid #ffcdd2",
              borderRadius: "16px",
              color: "#c62828",
              marginBottom: 40,
              display: "flex",
              alignItems: "center",
              gap: 12
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {results && <ResultsView results={results} runId={runId} />}
      </div>
      <div
        style={{
          position: "fixed",
          bottom: 24,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 100,
        }}
      >
        <HealthPill health={backendHealth} />
      </div>
    </main>
  );
}



function Spinner() {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: "#ffffff",
          }}
          animate={{
            y: [0, -6, 0],
            opacity: [0.6, 1, 0.6],
          }}
          transition={{
            duration: 0.8,
            repeat: Infinity,
            delay: i * 0.2,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

function HealthPill({
  health,
}: {
  health: { status: "unknown" | "ok" | "down"; latencyMs?: number; lastCheckedAt?: number };
}) {
  const isOk = health.status === "ok";
  const isDown = health.status === "down";

  const label = isOk ? "Systems Normal" : isDown ? "Offline" : "Connecting...";
  const color = isOk ? "#34c759" : isDown ? "#ff3b30" : "#86868b";

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 10px",
        borderRadius: 20,
        background: "rgba(255, 255, 255, 0.5)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        border: "1px solid rgba(0,0,0,0.06)",
        boxShadow: "0 2px 8px rgba(0,0,0,0.02)",
        transition: "all 0.2s ease",
        cursor: "default",
      }}
    >
      <div style={{ position: "relative", width: 6, height: 6 }}>
        <span
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            background: color,
            boxShadow: `0 0 6px ${color}`,
          }}
        />
        {isOk && (
          <motion.span
            initial={{ scale: 1, opacity: 0.5 }}
            animate={{ scale: 2.5, opacity: 0 }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              background: color,
            }}
          />
        )}
      </div>

      <span
        style={{
          fontSize: "12px",
          fontWeight: 500,
          color: "#48484a",
          letterSpacing: "-0.01em",
        }}
      >
        {label}
      </span>

      {health.latencyMs && isOk && (
        <span
          style={{
            fontSize: "11px",
            color: "#aeaeb2",
            fontWeight: 400,
            marginLeft: 2,
            fontFeatureSettings: "'tnum' on",
          }}
        >
          {health.latencyMs}ms
        </span>
      )}
    </div>
  );
}

function TextInput({
  value,
  onChange,
  placeholder,
  icon,
  hasError,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  icon?: ReactNode;
  hasError?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        background: "#ffffff",
        border: hasError ? "1px solid #ff3b30" : "1px solid #e5e5ea",
        borderRadius: "14px",
        padding: "0 16px",
        height: "54px",
        transition: "all 0.2s ease",
        boxShadow: hasError ? "0 0 0 2px rgba(255, 59, 48, 0.1)" : "none",
      }}
    >
      {icon}
      <input
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: "100%",
          padding: "16px 0",
          fontSize: "16px",
          border: "none",
          outline: "none",
          fontFamily: "inherit",
          backgroundColor: "transparent",
          fontWeight: 500,
          color: "#1d1d1f",
        }}
      />
    </div>
  );
}

const fieldContainerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 10,
};

const labelStyle: React.CSSProperties = {
  fontSize: "12px",
  fontWeight: 700,
  color: "#1d1d1f",
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  marginLeft: "4px",
};

function PillButton({
  label,
  selected,
  hasError,
  onClick,
}: {
  label: string;
  selected: boolean;
  hasError?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "10px 20px",
        fontSize: "14px",
        fontWeight: 600,
        fontFamily: "inherit",
        borderRadius: "100px",
        border: selected
          ? "2px solid #FF4F00"
          : hasError
            ? "2px solid #ff3b30"
            : "1.5px solid #e5e5ea",
        background: selected ? "rgba(255, 79, 0, 0.08)" : "#ffffff",
        color: selected ? "#FF4F00" : "#1d1d1f",
        cursor: "pointer",
        transition: "all 0.2s ease",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </button>
  );
}

const buttonStyle = (disabled: boolean): React.CSSProperties => ({
  marginLeft: "auto",
  padding: "0 40px",
  height: "56px",
  fontSize: "17px",
  fontWeight: 600,
  color: "#ffffff",
  background: disabled
    ? "#86868b"
    : "linear-gradient(135deg, #FF4F00 0%, #FF2E00 100%)",
  border: "none",
  borderRadius: "100px",
  cursor: disabled ? "not-allowed" : "pointer",
  transition: "all 0.2s ease",
  boxShadow: disabled ? "none" : "0 8px 20px rgba(255, 79, 0, 0.4)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: "auto",
  minWidth: "160px"
});
