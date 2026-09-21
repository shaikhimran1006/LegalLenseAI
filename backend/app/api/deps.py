"""FastAPI dependencies: workspace scoping, rate limiting, DB session."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Generator

from fastapi import Header, HTTPException, Request

from app.core.config import get_settings
from app.db.database import get_db

DEFAULT_WORKSPACE = "public"


def get_workspace_id(x_workspace_id: str | None = Header(default=None)) -> str:
    """Anonymous, opaque workspace separation. A client supplies an id (e.g.
    generated in localStorage) so documents are not visible to other devices.
    This is namespacing for a judge-friendly demo, not a full auth system."""
    if not x_workspace_id or not x_workspace_id.strip():
        return DEFAULT_WORKSPACE
    value = x_workspace_id.strip()
    if not (2 <= len(value) <= 64) or not value.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid workspace id.")
    return value


# ---------------------------------------------------------------------------
# In-memory sliding-window rate limiter (best effort; per process)
# ---------------------------------------------------------------------------

_rate_buckets: dict[str, deque] = defaultdict(deque)


def rate_limit(max_requests: int | None = None, window_seconds: int = 60):
    max_requests = max_requests or get_settings().rate_limit_per_minute

    def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        origin = request.headers.get("origin") or "-"
        key = f"{client_ip}::{origin}"
        now = time.monotonic()
        bucket = _rate_buckets[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= max_requests:
            raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
        bucket.append(now)

    return dependency


def get_db_dependency():
    return get_db