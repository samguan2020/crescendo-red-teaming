"""
Arq task queue - enqueues jobs into Redis for a separate worker process to
execute (see worker.py). Survives API restarts, supports retries/scaling.
Implements TaskQueuePort.

arq is imported lazily so the package can run in `inprocess` mode without arq
installed.
"""
from __future__ import annotations

RUN_ATTACK_TASK = "run_attack_job"


class ArqQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pool = None

    async def _ensure_pool(self):
        if self._pool is None:
            from arq import create_pool
            from arq.connections import RedisSettings

            self._pool = await create_pool(RedisSettings.from_dsn(self._redis_url))
        return self._pool

    async def enqueue(self, job_id: str) -> None:
        pool = await self._ensure_pool()
        await pool.enqueue_job(RUN_ATTACK_TASK, job_id)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
