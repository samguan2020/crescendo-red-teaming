"""
Application-wide error types and the FastAPI exception handlers.

Centralizing this removes the per-route try/except + traceback boilerplate the
PoC had in every endpoint.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from crescendo.application.query_attack import JobNotFoundError
from crescendo.application.submit_attack import InvalidModelsError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(JobNotFoundError)
    async def _not_found(request: Request, exc: JobNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidModelsError)
    async def _invalid_models(request: Request, exc: InvalidModelsError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "available": exc.available},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
