"""
CachedDurableJobRepository - composes Postgres (truth) + Redis (projection).

Write policy (decision: Postgres = source of truth):
  - The Postgres write is authoritative and awaited; failure propagates.
  - The Redis projection write is best-effort (logged on failure) since it can
    always be rebuilt from Postgres.
Reads serve the Redis projection for fast polling, falling back to Postgres
(and re-warming the projection) on a cache miss.
"""
from __future__ import annotations

import logging

from crescendo.adapters.persistence.postgres_store import PostgresJobStore
from crescendo.adapters.persistence.redis_projection import RedisJobProjection
from crescendo.domain.models import AttackJob, JobStatus, Turn, Verdict

logger = logging.getLogger(__name__)


class CachedDurableJobRepository:
    """Implements JobRepositoryPort."""

    def __init__(self, store: PostgresJobStore, projection: RedisJobProjection) -> None:
        self._store = store
        self._projection = projection

    async def _project(self, coro_desc: str, coro) -> None:
        try:
            await coro
        except Exception as e:  # noqa: BLE001 - projection is best-effort
            logger.warning("Redis projection %s failed: %s", coro_desc, e)

    async def save(self, job: AttackJob) -> None:
        await self._store.create_job(job)
        await self._project("init_job", self._projection.init_job(job))

    async def get(self, job_id: str) -> AttackJob | None:
        try:
            cached = await self._projection.get_job(job_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis projection read failed: %s", e)
            cached = None
        if cached is not None:
            return cached
        job = await self._store.load_job(job_id)
        if job is not None:
            await self._project("rewarm", self._projection.init_job(job))
        return job

    async def append_turn(self, job_id: str, model: str, turn: Turn) -> None:
        await self._store.append_turn(job_id, model, turn)
        await self._project(
            "append_turn", self._projection.append_turn(job_id, model, turn)
        )

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error: str | None = None,
        total_duration_ms: float | None = None,
    ) -> None:
        await self._store.update_job_status(
            job_id, status, error=error, total_duration_ms=total_duration_ms
        )
        patch: dict = {"status": status.value}
        if error is not None:
            patch["error"] = error
        if total_duration_ms is not None:
            patch["total_duration_ms"] = total_duration_ms
        await self._project("patch_meta", self._projection.patch_meta(job_id, patch))

    async def update_model_run(
        self,
        job_id: str,
        model: str,
        *,
        status: JobStatus,
        final_output: str | None = None,
        final_verdict: Verdict | None = None,
    ) -> None:
        await self._store.update_model_run(
            job_id,
            model,
            status=status,
            final_output=final_output,
            final_verdict=final_verdict,
        )
        await self._project(
            "patch_run",
            self._projection.patch_run(
                job_id,
                model,
                {
                    "status": status.value,
                    "final_output": final_output,
                    "final_verdict": final_verdict.value if final_verdict else None,
                },
            ),
        )
