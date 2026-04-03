"""
Request middleware for structured logging, request IDs, and simple rate limiting.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .settings import get_settings


logger = logging.getLogger("intellicredit.api")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        payload = {
            "event": "http_request",
            "request_id": getattr(request.state, "request_id", None),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": request.client.host if request.client else None,
        }
        logger.info(json.dumps(payload))
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next):
        if not self.settings.enable_rate_limit or request.url.path == "/health":
            return await call_next(request)

        identifier = request.client.host if request.client else "unknown"
        bucket_key = f"{identifier}:{request.url.path}"
        now = time.time()
        window_seconds = 60

        with self._lock:
            bucket = self._hits[bucket_key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()

            if len(bucket) >= self.settings.rate_limit_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                )

            bucket.append(now)

        return await call_next(request)
