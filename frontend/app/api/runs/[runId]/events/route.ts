import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "edge"; // Use edge runtime for better streaming support

export async function GET(
    request: NextRequest,
    context: { params: Promise<{ runId: string }> }
) {
    const { runId } = await context.params;

    // Fetch SSE stream from backend
    const backendUrl = `http://localhost:8000/api/runs/${runId}/events`;

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

        // Create a TransformStream to pass through the SSE data
        const { readable, writable } = new TransformStream();
        const writer = writable.getWriter();
        const reader = response.body.getReader();

        // Stream data from backend to client
        (async () => {
            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    await writer.write(value);
                }
            } catch {
                // Connection closed
            } finally {
                try {
                    await writer.close();
                } catch {
                    // Already closed
                }
            }
        })();

        return new Response(readable, {
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
