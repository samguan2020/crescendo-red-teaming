"""
Composition root - wires every adapter to the application/domain ports.

One builder used by both runtimes:
- the API process (FastAPI lifespan), and
- the Arq worker process (worker.py),
so dependency wiring lives in exactly one place.
"""
from __future__ import annotations

import logging

from crescendo.adapters.judge.regex_judge import RegexJudge
from crescendo.adapters.llm.gemini_attacker import GeminiAttacker
from crescendo.adapters.llm.huggingface_target import HuggingFaceTarget
from crescendo.adapters.persistence.postgres_store import PostgresJobStore
from crescendo.adapters.persistence.redis_client import (
    BaseRedisClient,
    InMemoryRedisClient,
    LocalRedisClient,
)
from crescendo.adapters.persistence.redis_projection import RedisJobProjection
from crescendo.adapters.persistence.repository import CachedDurableJobRepository
from crescendo.adapters.queue.arq_queue import ArqQueue
from crescendo.adapters.queue.inprocess import InProcessQueue
from crescendo.application.attack_engine import AttackEngine
from crescendo.application.query_attack import QueryAttackUseCase
from crescendo.application.run_job import RunJobUseCase
from crescendo.application.submit_attack import SubmitAttackUseCase
from crescendo.infra.config import Settings

logger = logging.getLogger(__name__)


class Container:
    """Holds wired singletons and lifecycle hooks."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        self.redis: BaseRedisClient = (
            InMemoryRedisClient()
            if settings.USE_MEMORY_STORE and not settings.REDIS_URL
            else LocalRedisClient(settings.REDIS_URL)
        )
        self.store = PostgresJobStore(settings.DATABASE_URL)
        self.projection = RedisJobProjection(self.redis, ttl=settings.JOB_TTL)
        self.repo = CachedDurableJobRepository(self.store, self.projection)

        self.judge = RegexJudge()
        self.target = HuggingFaceTarget(
            api_key=settings.HUGGINGFACE_API_KEY,
            model_map=settings.HUGGINGFACE_MODELS,
            api_url=settings.HUGGINGFACE_API_URL,
        )
        self.attacker = GeminiAttacker(
            model=settings.GEMINI_MODEL,
            api_key=settings.GOOGLE_API_KEY,
        )
        self.engine = AttackEngine(repo=self.repo, target=self.target, judge=self.judge)
        self.run_job = RunJobUseCase(
            repo=self.repo, engine=self.engine, attacker=self.attacker
        )

        if settings.TASK_QUEUE == "arq":
            self.queue = ArqQueue(settings.REDIS_URL)
        else:
            inproc = InProcessQueue()
            inproc.set_runner(self.run_job.execute)
            self.queue = inproc

        self.submit_attack = SubmitAttackUseCase(
            repo=self.repo,
            queue=self.queue,
            available_models=settings.AVAILABLE_MODELS,
        )
        self.query_attack = QueryAttackUseCase(repo=self.repo)

    async def startup(self, *, create_schema: bool = False) -> None:
        await self.redis.connect()
        if create_schema:
            await self.store.create_schema()
        logger.info(
            "Container started (queue=%s, redis=%s)",
            self.settings.TASK_QUEUE,
            type(self.redis).__name__,
        )

    async def shutdown(self) -> None:
        try:
            await self.redis.disconnect()
        except Exception:  # noqa: BLE001
            pass
        try:
            await self.store.dispose()
        except Exception:  # noqa: BLE001
            pass
        close = getattr(self.queue, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:  # noqa: BLE001
                pass


async def build_container(settings: Settings, *, create_schema: bool = False) -> Container:
    container = Container(settings)
    await container.startup(create_schema=create_schema)
    return container
