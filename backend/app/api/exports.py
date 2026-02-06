from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response

router = APIRouter(prefix="/api")


def _render_spot_on_markdown(final_output: dict[str, Any]) -> str:
    constraints = final_output.get("constraints") or {}
    destination = constraints.get("destination") or "Destination"
    out: list[str] = [f"# Spot On — {destination}", ""]

    def _section(title: str, items: list[dict[str, Any]], key_name: str = "name") -> None:
        if not items:
            return
        out.append(f"## {title}")
        for item in items:
            name = item.get(key_name) or "Item"
            url = item.get("url")
            line = f"- **{name}**"
            if url:
                line += f" — {url}"
            snippet = item.get("snippet")
            why = item.get("why_recommended")
            if why:
                line += f"  \n  _Why:_ {why}"
            elif snippet:
                line += f"  \n  _Note:_ {snippet}"
            if item.get("hours_text"):
                line += f"  \n  _Hours:_ {item['hours_text']}"
            if item.get("address"):
                line += f"  \n  _Address:_ {item['address']}"
            out.append(line)
        out.append("")

    _section("🍽️ Restaurants", final_output.get("restaurants") or [])
    _section("🏛️ Must-See Spots", final_output.get("travel_spots") or [])
    _section("🏨 Hotels", final_output.get("hotels") or [])
    _section("🚗 Car Rentals", final_output.get("car_rentals") or [], key_name="provider")
    _section("✈️ Flights", final_output.get("flights") or [], key_name="route")

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
    final_output = doc.get("final_output")

    if not final_output:
        raise HTTPException(
            status_code=409,
            detail="Run output not ready (legacy itinerary exports are not supported)",
        )

    if format == "json":
        content = json.dumps(final_output, ensure_ascii=False, indent=2).encode("utf-8")
        filename = "spot-on"
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}-{runId}.json"'},
        )

    md = _render_spot_on_markdown(final_output)
    filename = f"spot-on-{runId}.md"

    return PlainTextResponse(
        content=md,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        media_type="text/markdown; charset=utf-8",
    )
