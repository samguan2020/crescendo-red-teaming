"""
FastAPI application entrypoint.

Builds the DI container in the lifespan, mounts routes under /api/v1, wires
CORS + API key middleware and global exception handlers. Run with:
    uvicorn crescendo.main:app
"""
from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from crescendo.adapters.inbound.http.middleware import APIKeyMiddleware
from crescendo.adapters.inbound.http.routes import router as api_router
from crescendo.infra.config import get_settings
from crescendo.infra.container import Container
from crescendo.infra.errors import register_exception_handlers
from crescendo.infra.observability import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    container = Container(settings)
    # Auto-create schema in dev; prod should run Alembic migrations.
    await container.startup(create_schema=settings.ENV == "dev")
    # Verify Redis round-trip so a misconfigured deploy fails loudly.
    probe = f"startup-probe:{secrets.token_hex(4)}"
    await container.redis.set(probe, "ok", ttl=10)
    if await container.redis.get(probe) != "ok":
        raise RuntimeError("Redis round-trip failed during startup probe")
    app.state.container = container
    try:
        yield
    finally:
        await container.shutdown()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Crescendo Backend",
        description="Multi-turn crescendo jailbreak evaluation across open-source models.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(APIKeyMiddleware, api_key=settings.API_KEY)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/")
    async def root():
        return {"name": settings.APP_NAME, "version": "1.0.0", "docs": "/docs"}

    @app.get("/health")
    async def health():
        container: Container = app.state.container
        redis_ok = False
        try:
            probe = f"health:{secrets.token_hex(4)}"
            await container.redis.set(probe, "ok", ttl=10)
            redis_ok = (await container.redis.get(probe)) == "ok"
            await container.redis.delete(probe)
        except Exception:  # noqa: BLE001
            redis_ok = False
        db_ok = await container.store.ping()
        status_str = "healthy" if redis_ok and db_ok else "degraded"
        return {
            "status": status_str,
            "redis": "connected" if redis_ok else "disconnected",
            "database": "connected" if db_ok else "disconnected",
            "queue": settings.TASK_QUEUE,
        }

    return app


app = create_app()
