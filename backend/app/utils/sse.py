import json
from typing import Any

def sse_event(event: str, data: dict[str, Any]) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    msg = f"event: {event}\ndata: {payload}\n\n"
    return msg.encode("utf-8")
