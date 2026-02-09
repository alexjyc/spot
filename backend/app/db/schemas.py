from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.spot_on import TravelConstraints

RunStatus = Literal["queued", "running", "done", "error", "cancelled"]
NodeStatus = Literal["start", "end", "error"]


class NodeEventPayload(BaseModel):
    node: str
    status: NodeStatus
    message: str | None = None
    durationMs: int | None = None
    error: str | None = None


class RunProgress(BaseModel):
    nodes: dict[str, NodeEventPayload] = Field(default_factory=dict)


class RunCreateRequest(BaseModel):
    """Create a Spot On run.

    Provide structured `constraints`. Prompt-only runs are not supported.
    """

    constraints: TravelConstraints | None = None
    # Reserved for feature flags.
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_constraints(self) -> "RunCreateRequest":
        if not self.constraints:
            raise ValueError("Provide 'constraints'")
        return self


class RunCreateResponse(BaseModel):
    runId: str


class RunError(BaseModel):
    message: str


class RunGetResponse(BaseModel):
    runId: str
    status: RunStatus
    updatedAt: datetime
    progress: RunProgress | None = None
    constraints: dict[str, Any] | None = None
    final_output: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    error: RunError | None = None
    durationMs: int | None = None


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
