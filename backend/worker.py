"""
Arq worker entrypoint (used only when TASK_QUEUE=arq).

Run with:  arq worker.WorkerSettings

Executes queued attack jobs in a separate process from the API, so jobs
survive API restarts and can be retried/scaled independently.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from arq.connections import RedisSettings  # noqa: E402

from crescendo.adapters.queue.arq_queue import RUN_ATTACK_TASK  # noqa: E402
from crescendo.infra.config import get_settings  # noqa: E402
from crescendo.infra.container import Container  # noqa: E402
from crescendo.infra.observability import configure_logging  # noqa: E402


async def run_attack_job(ctx, job_id: str) -> None:
    await ctx["container"].run_job.execute(job_id)


# arq dispatches by function name; keep it aligned with the enqueue task name.
run_attack_job.__name__ = RUN_ATTACK_TASK


async def _startup(ctx) -> None:
    configure_logging()
    container = Container(get_settings())
    await container.startup(create_schema=False)
    ctx["container"] = container


async def _shutdown(ctx) -> None:
    await ctx["container"].shutdown()


class WorkerSettings:
    functions = [run_attack_job]
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
