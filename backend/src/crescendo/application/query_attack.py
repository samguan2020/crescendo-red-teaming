"""
QueryAttackUseCase - read job status/results for polling and trace export.
"""
from __future__ import annotations

from crescendo.domain.models import AttackJob
from crescendo.domain.ports import JobRepositoryPort


class JobNotFoundError(LookupError):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Job {job_id} not found")


class QueryAttackUseCase:
    def __init__(self, *, repo: JobRepositoryPort) -> None:
        self._repo = repo

    async def get(self, job_id: str) -> AttackJob:
        job = await self._repo.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job
