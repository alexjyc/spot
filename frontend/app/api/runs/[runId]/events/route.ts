import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(
    request: NextRequest,
    context: { params: Promise<{ runId: string }> }
) {
    const { runId } = await context.params;

    // Fetch SSE stream from backend
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const backendUrl = `${baseUrl}/api/runs/${runId}/events`;

    try {
        const response = await fetch(backendUrl, {
            method: "GET",
            headers: {
                Accept: "text/event-stream",
                "Cache-Control": "no-cache",
                Connection: "keep-alive",
            },
        });

        if (!response.ok) {
            return new Response(`Backend error: ${response.status}`, {
                status: response.status,
            });
        }

        if (!response.body) {
            return new Response("No response body", { status: 500 });
        }

        return new Response(response.body, {
            status: 200,
            headers: {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        });
    } catch (error) {
        console.error("SSE proxy error:", error);
        return new Response("Failed to connect to backend", { status: 502 });
    }
}
