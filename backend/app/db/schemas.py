from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


RunStatus = Literal["queued", "running", "done", "error"]


class RunOptions(BaseModel):
    country: str | None = None
    days: int | None = None
    pace: Literal["relaxed", "standard", "packed"] | None = None
    budget: int | None = None
    interests: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    must_do: list[str] = Field(default_factory=list)
    special_instructions: str | None = None


class RunCreateRequest(BaseModel):
    prompt: str
    options: RunOptions | None = None


class RunCreateResponse(BaseModel):
    runId: str


class RunError(BaseModel):
    message: str


class Citation(BaseModel):
    itemId: str
    urls: list[str]


class ItinerarySlotItem(BaseModel):
    id: str
    name: str
    kind: str
    url: str | None = None
    area: str | None = None
    address: str | None = None
    durationMin: int | None = None
    priceHint: str | None = None
    hoursText: str | None = None
    reservation: str | None = None
    ticketing: str | None = None
    notes: str | None = None


class ItinerarySlot(BaseModel):
    label: str
    items: list[ItinerarySlotItem]


class ItineraryDay(BaseModel):
    dateLabel: str | None = None
    slots: list[ItinerarySlot]


class Itinerary(BaseModel):
    title: str
    city: str | None = None
    days: list[ItineraryDay]
    markdown: str | None = None


class RunGetResponse(BaseModel):
    runId: str
    status: RunStatus
    updatedAt: datetime
    constraints: dict[str, Any] | None = None
    itinerary: Itinerary | None = None
    final_output: dict[str, Any] | None = None  # For Spot On system
    warnings: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    error: RunError | None = None
    durationMs: int | None = None


class Candidate(BaseModel):
    id: str
    name: str
    kind: str
    category: str | None = None  # e.g. restaurant|activity|reference (UI hint only)
    tags: list[str] = Field(default_factory=list)
    area: str | None = None
    url: str
    snippet: str | None = None
    why: str | None = None
    estDurationMin: int | None = None
    priceHint: str | None = None
    timeOfDayFit: list[str] = Field(default_factory=list)
    mealFit: list[str] = Field(default_factory=list)
    weatherFit: str | None = None  # indoor|outdoor|either
    energy: str | None = None  # low|medium|high
    reservationLikelihood: str | None = None  # low|medium|high (heuristic)
    accessibilityHints: list[str] = Field(default_factory=list)
    source: Literal["tavily_search"] = "tavily_search"


class ShortlistSlot(BaseModel):
    label: str
    primary: list[str] = Field(default_factory=list)  # candidate ids
    alternatives: list[str] = Field(default_factory=list)  # candidate ids


class ShortlistDay(BaseModel):
    dateLabel: str | None = None
    slots: list[ShortlistSlot]


class Shortlist(BaseModel):
    days: list[ShortlistDay]


class VerifiedItem(BaseModel):
    candidateId: str
    name: str
    url: str
    address: str | None = None
    area: str | None = None
    hoursText: str | None = None
    hours: dict[str, Any] | None = None  # optional structured hours when parseable
    closedDays: list[str] = Field(default_factory=list)
    reservation: str | None = None
    ticketing: str | None = None
    priceHint: str | None = None
    warnings: list[str] = Field(default_factory=list)
    confidence: str | None = None  # high|medium|low


class RunEvent(BaseModel):
    runId: str
    ts: datetime
    type: Literal["node", "artifact", "log"]
    node: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    runId: str
    ts: datetime
    type: str
    payload: dict[str, Any]
    version: int = 1
