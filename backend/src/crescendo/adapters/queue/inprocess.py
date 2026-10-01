"""
In-process task queue - schedules execution as an asyncio task in the API
process. Simplest runtime; jobs are lost on restart (acceptable for local/PoC).
Implements TaskQueuePort.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class InProcessQueue:
    def __init__(self) -> None:
        self._runner: Callable[[str], Awaitable[None]] | None = None
        self._tasks: set[asyncio.Task] = set()

    def set_runner(self, runner: Callable[[str], Awaitable[None]]) -> None:
        self._runner = runner

    async def enqueue(self, job_id: str) -> None:
        if self._runner is None:
            raise RuntimeError("InProcessQueue runner not configured")
        task = asyncio.create_task(self._run(job_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, job_id: str) -> None:
        try:
            await self._runner(job_id)  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            logger.exception("In-process job %s crashed", job_id)
