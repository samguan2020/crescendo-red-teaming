"""API key middleware - requires X-API-Key on /api/v1/* when API_KEY is set."""
from __future__ import annotations

import secrets

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        if not self._api_key:
            return await call_next(request)
        path = request.url.path
        if path in _PUBLIC_PATHS or not path.startswith("/api/v1"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        provided = request.headers.get("x-api-key")
        if not provided or not secrets.compare_digest(provided, self._api_key):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or missing API key"},
            )
        return await call_next(request)
