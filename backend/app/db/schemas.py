from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

RunStatus = Literal["queued", "running", "done", "error"]


class RunCreateRequest(BaseModel):
    """Create a Spot On run.

    Provide either:
    - `prompt` (free-form text) OR
    - `constraints` (structured input from UI dropdowns/forms).
    """

    prompt: str | None = None
    constraints: dict[str, Any] | None = None
    # Reserved for future feature flags. Current Spot On graph ignores options.
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_prompt_or_constraints(self) -> "RunCreateRequest":
        if not (self.prompt and self.prompt.strip()) and not self.constraints:
            raise ValueError("Provide either 'prompt' or 'constraints'")
        return self


class RunCreateResponse(BaseModel):
    runId: str


class RunError(BaseModel):
    message: str


class RunGetResponse(BaseModel):
    runId: str
    status: RunStatus
    updatedAt: datetime
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

