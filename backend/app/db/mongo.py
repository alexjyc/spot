from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MongoService:
    def __init__(self, mongodb_uri: str, db_name: str) -> None:
        if not mongodb_uri:
            raise ValueError("MONGODB_URI is required")
        self.client = AsyncIOMotorClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self.runs = self.db["runs"]
        self.run_events = self.db["run_events"]
        self.artifacts = self.db["artifacts"]

    def close(self) -> None:
        self.client.close()

    async def ping(self) -> None:
        await self.client.admin.command("ping")

    async def ensure_indexes(self) -> None:
        await self.runs.create_index([("updatedAt", ASCENDING)])
        await self.runs.create_index([("status", ASCENDING), ("updatedAt", ASCENDING)])
        await self.run_events.create_index(
            [("runId", ASCENDING), ("ts", ASCENDING), ("_id", ASCENDING)]
        )
        await self.artifacts.create_index(
            [("runId", ASCENDING), ("ts", ASCENDING), ("_id", ASCENDING)]
        )

    async def create_run(
        self,
        run_id: str,
        *,
        prompt: str | None,
        constraints: dict[str, Any] | None,
        options: dict[str, Any],
    ) -> None:
        doc = {
            "_id": run_id,
            "status": "queued",
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
            "prompt": prompt or "",
            "options": options,
            "constraints": constraints,
            "warnings": [],
            "final_output": None,
            "error": None,
            "runType": "spot_on",
            "apiVersion": 1,
        }
        await self.runs.insert_one(doc)

    async def update_run(self, run_id: str, patch: dict[str, Any]) -> None:
        patch = dict(patch)
        patch["updatedAt"] = utc_now()
        await self.runs.update_one({"_id": run_id}, {"$set": patch})

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return await self.runs.find_one({"_id": run_id})

    async def append_event(
        self,
        run_id: str,
        *,
        type: str,
        node: str | None = None,
        payload: dict[str, Any] | None = None,
        ts: datetime | None = None,
    ) -> None:
        doc = {
            "runId": run_id,
            "ts": ts or utc_now(),
            "type": type,
            "node": node,
            "payload": payload or {},
        }
        await self.run_events.insert_one(doc)

    async def add_artifact(
        self,
        run_id: str,
        *,
        type: str,
        payload: dict[str, Any],
        version: int = 1,
    ) -> None:
        doc = {
            "runId": run_id,
            "ts": utc_now(),
            "type": type,
            "payload": payload,
            "version": version,
        }
        await self.artifacts.insert_one(doc)
        await self.append_event(
            run_id, type="artifact", payload={"type": type, "payload": payload}
        )

    async def list_events_since(
        self, run_id: str, since: datetime
    ) -> list[dict[str, Any]]:
        cursor = (
            self.run_events.find({"runId": run_id, "ts": {"$gt": since}})
            .sort("ts", ASCENDING)
            .limit(200)
        )
        return await cursor.to_list(length=200)

    async def list_events_since_cursor(
        self,
        run_id: str,
        *,
        since_ts: datetime,
        since_id: Any | None,
    ) -> list[dict[str, Any]]:
        if since_id is None:
            q = {"runId": run_id, "ts": {"$gt": since_ts}}
        else:
            q = {
                "runId": run_id,
                "$or": [
                    {"ts": {"$gt": since_ts}},
                    {"ts": since_ts, "_id": {"$gt": since_id}},
                ],
            }
        cursor = (
            self.run_events.find(q)
            .sort([("ts", ASCENDING), ("_id", ASCENDING)])
            .limit(200)
        )
        return await cursor.to_list(length=200)
