import { NextRequest } from "next/server";
import { backendUrl } from "../../../../../lib/proxy";

export async function GET(
    request: NextRequest,
    context: { params: Promise<{ runId: string }> }
) {
    const { runId } = await context.params;

    try {
        const res = await fetch(backendUrl(`/runs/${runId}/export/xlsx`));
        if (!res.ok) {
            const text = await res.text().catch(() => "");
            return new Response(text || `Backend error: ${res.status}`, { status: res.status });
        }
        return new Response(res.body, {
            status: 200,
            headers: {
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Content-Disposition": res.headers.get("Content-Disposition") || `attachment; filename="spot-on-${runId}.xlsx"`,
            },
        });
    } catch {
        return new Response("Failed to connect to backend", { status: 502 });
    }
}
