"""
SubmitAttackUseCase - validate input, create+persist a queued job, enqueue it.

The actual execution happens in a worker (in-process or external) via the
TaskQueuePort, decoupling the long-running attack from the HTTP request.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from crescendo.domain.models import AttackJob, StrategyKind
from crescendo.domain.ports import JobRepositoryPort, TaskQueuePort


class InvalidModelsError(ValueError):
    def __init__(self, invalid: list[str], available: list[str]) -> None:
        self.invalid = invalid
        self.available = available
        super().__init__(f"Invalid models: {invalid}. Available: {available}")


@dataclass
class SubmitAttackCommand:
    objective: str
    models: list[str]
    strategy: StrategyKind
    temperature: float = 0.7
    max_turns: int = 10
    seed: int | None = None


class SubmitAttackUseCase:
    def __init__(
        self,
        *,
        repo: JobRepositoryPort,
        queue: TaskQueuePort,
        available_models: list[str],
    ) -> None:
        self._repo = repo
        self._queue = queue
        self._available = available_models

    async def execute(self, cmd: SubmitAttackCommand) -> AttackJob:
        invalid = [m for m in cmd.models if m not in self._available]
        if invalid:
            raise InvalidModelsError(invalid, self._available)

        job = AttackJob.create(
            job_id=str(uuid.uuid4()),
            objective=cmd.objective,
            models=cmd.models,
            strategy_kind=cmd.strategy,
            max_turns=cmd.max_turns,
            temperature=cmd.temperature,
            seed=cmd.seed,
        )
        await self._repo.save(job)
        await self._queue.enqueue(job.id)
        return job
