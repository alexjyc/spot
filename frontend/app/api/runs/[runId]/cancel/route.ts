import { NextRequest, NextResponse } from "next/server";
import { backendUrl } from "../../../../../lib/proxy";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ runId: string }> }
) {
  const { runId } = await context.params;

  try {
    const res = await fetch(backendUrl(`/api/runs/${runId}/cancel`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ ok: false }, { status: 502 });
  }
}
