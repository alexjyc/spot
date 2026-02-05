"use client";
import { useState } from "react";
import ResultsView from "../components/ResultsView";

export default function Page() {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [departingDate, setDepartingDate] = useState("");
  const [returningDate, setReturningDate] = useState("");
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults(null);

    const prompt = `From ${origin} to ${destination}, departing ${departingDate}${
      returningDate ? `, returning ${returningDate}` : ""
    }`;

    try {
      const res = await fetch("/api/runs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt, options: {} }),
      });

      if (!res.ok) {
        throw new Error("Failed to create run");
      }

      const { runId } = await res.json();

      // Poll for results
      const pollInterval = setInterval(async () => {
        try {
          const runRes = await fetch(`/api/runs/${runId}`);
          const run = await runRes.json();

          if (run.status === "done") {
            setResults(run.final_output);
            setLoading(false);
            clearInterval(pollInterval);
          } else if (run.status === "error") {
            setError(run.error?.message || "Run failed");
            setLoading(false);
            clearInterval(pollInterval);
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 2000);

      // Timeout after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (loading) {
          setError("Request timed out");
          setLoading(false);
        }
      }, 120000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setLoading(false);
    }
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #f5f5f7 0%, #ffffff 100%)",
        padding: "60px 20px",
      }}
    >
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <header style={{ textAlign: "center", marginBottom: 60 }}>
          <h1
            style={{
              fontSize: "clamp(42px, 6vw, 56px)",
              fontWeight: 700,
              color: "#1d1d1f",
              margin: 0,
              letterSpacing: "-0.03em",
              lineHeight: 1.05,
            }}
          >
            Spot On ✈️
          </h1>
          <p
            style={{
              fontSize: "19px",
              color: "#86868b",
              marginTop: "16px",
              maxWidth: "560px",
              margin: "16px auto 0",
              lineHeight: 1.5,
            }}
          >
            Fast travel recommendations for restaurants, attractions, hotels,
            and transport.
          </p>
        </header>

        <form onSubmit={handleSubmit} style={{ marginBottom: 60 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 20,
              marginBottom: 24,
            }}
          >
            <input
              placeholder="Origin (e.g., Tokyo)"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              required
              style={inputStyle}
            />
            <input
              placeholder="Destination (e.g., Seoul)"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              required
              style={inputStyle}
            />
            <input
              type="date"
              value={departingDate}
              onChange={(e) => setDepartingDate(e.target.value)}
              required
              style={inputStyle}
              placeholder="Departing date"
            />
            <input
              type="date"
              value={returningDate}
              onChange={(e) => setReturningDate(e.target.value)}
              style={inputStyle}
              placeholder="Return date (optional)"
            />
          </div>
          <button type="submit" disabled={loading} style={buttonStyle(loading)}>
            {loading ? "Searching..." : "Find Recommendations"}
          </button>
        </form>

        {error && (
          <div
            style={{
              padding: 20,
              background: "#ffebee",
              borderRadius: 12,
              color: "#c62828",
              marginBottom: 40,
            }}
          >
            {error}
          </div>
        )}

        {results && <ResultsView results={results} />}
      </div>
    </main>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "16px 20px",
  fontSize: "17px",
  border: "1px solid #d2d2d7",
  borderRadius: 12,
  outline: "none",
  fontFamily: "inherit",
  backgroundColor: "#ffffff",
  transition: "border-color 0.2s",
};

const buttonStyle = (disabled: boolean): React.CSSProperties => ({
  width: "100%",
  padding: "18px 32px",
  fontSize: "17px",
  fontWeight: 600,
  color: "#ffffff",
  background: disabled
    ? "#d2d2d7"
    : "linear-gradient(135deg, #0071e3 0%, #005bb5 100%)",
  border: "none",
  borderRadius: 12,
  cursor: disabled ? "not-allowed" : "pointer",
  transition: "transform 0.1s, box-shadow 0.2s",
  boxShadow: disabled ? "none" : "0 4px 16px rgba(0, 113, 227, 0.24)",
});
