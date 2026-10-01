"""
RunJobUseCase - what a worker invokes to actually execute a queued job.

Shared by every TaskQueuePort runtime (in-process and Arq) so execution logic
lives in exactly one place.
"""
from __future__ import annotations

import logging

from crescendo.application.attack_engine import AttackEngine
from crescendo.domain.ports import AttackerLLMPort, JobRepositoryPort
from crescendo.strategies.factory import make_strategy_factory

logger = logging.getLogger(__name__)


class RunJobUseCase:
    def __init__(
        self,
        *,
        repo: JobRepositoryPort,
        engine: AttackEngine,
        attacker: AttackerLLMPort,
    ) -> None:
        self._repo = repo
        self._engine = engine
        self._attacker = attacker

    async def execute(self, job_id: str) -> None:
        job = await self._repo.get(job_id)
        if job is None:
            logger.error("RunJob: job %s not found; cannot execute", job_id)
            return
        factory = make_strategy_factory(job.strategy_kind, self._attacker)
        await self._engine.run(job, factory)
