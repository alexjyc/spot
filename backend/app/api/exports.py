from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response

router = APIRouter(prefix="/api")


def _render_markdown(itinerary: dict[str, Any]) -> str:
    title = itinerary.get("title") or "Itinerary"
    city = itinerary.get("city")
    out: list[str] = [f"# {title}"]
    if city:
        out.append(f"**City:** {city}")
    out.append("")
    for i, day in enumerate(itinerary.get("days") or []):
        label = day.get("dateLabel") or f"Day {i + 1}"
        out.append(f"## {label}")
        for slot in day.get("slots") or []:
            out.append(f"### {slot.get('label')}")
            for item in slot.get("items") or []:
                name = item.get("name") or "Item"
                url = item.get("url")
                line = f"- **{name}**"
                if url:
                    line += f" — {url}"
                if item.get("hoursText"):
                    line += f"  \n  _Hours:_ {item['hoursText']}"
                if item.get("address"):
                    line += f"  \n  _Address:_ {item['address']}"
                out.append(line)
        out.append("")
    return "\n".join(out).strip() + "\n"


@router.get("/runs/{runId}/export")
async def export_run(
    runId: str,
    request: Request,
    format: Literal["markdown", "json"] = Query(default="markdown"),
):
    deps = getattr(request.app.state, "deps", None)
    mongo = getattr(deps, "mongo", None) if deps else None
    if not mongo:
        raise HTTPException(status_code=500, detail="MongoDB is not configured")
    doc = await mongo.get_run(runId)
    if not doc:
        raise HTTPException(status_code=404, detail="Run not found")
    itinerary = doc.get("itinerary")
    if not itinerary:
        raise HTTPException(status_code=409, detail="Itinerary not ready")

    if format == "json":
        content = json.dumps(itinerary, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="itinerary-{runId}.json"'
            },
        )

    md = itinerary.get("markdown") or _render_markdown(itinerary)
    return PlainTextResponse(
        content=md,
        headers={"Content-Disposition": f'attachment; filename="itinerary-{runId}.md"'},
        media_type="text/markdown; charset=utf-8",
    )
