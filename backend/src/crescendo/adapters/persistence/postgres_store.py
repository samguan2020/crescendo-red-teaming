"""
Postgres store - the source of truth. Incremental, concurrency-friendly writes
(each model task writes only its own run/turns).
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from crescendo.domain.models import (
    AttackJob,
    JobStatus,
    ModelRun,
    StrategyKind,
    Turn,
    Verdict,
)
from crescendo.adapters.persistence.orm import (
    AttackJobRow,
    Base,
    ModelRunRow,
    TurnRow,
)

logger = logging.getLogger(__name__)


def normalize_dsn(url: str) -> str:
    """Accept postgres:// or postgresql:// and convert to asyncpg DSN."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


class PostgresJobStore:
    def __init__(self, dsn: str) -> None:
        self._engine = create_async_engine(
            normalize_dsn(dsn), pool_pre_ping=True, pool_size=5, max_overflow=5
        )
        self._session: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    async def create_schema(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def ping(self) -> bool:
        from sqlalchemy import text

        try:
            async with self._session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("Postgres ping failed: %s", e)
            return False

    async def dispose(self) -> None:
        await self._engine.dispose()

    # ---- writes -------------------------------------------------------

    async def create_job(self, job: AttackJob) -> None:
        async with self._session() as session, session.begin():
            session.add(
                AttackJobRow(
                    id=job.id,
                    objective=job.objective,
                    strategy_kind=job.strategy_kind.value,
                    max_turns=job.max_turns,
                    temperature=job.temperature,
                    seed=job.seed,
                    status=job.status.value,
                    created_at=job.created_at,
                )
            )
            for model in job.models:
                session.add(ModelRunRow(job_id=job.id, model=model, status="queued"))

    async def _run_id(self, session: AsyncSession, job_id: str, model: str) -> int | None:
        res = await session.execute(
            select(ModelRunRow.id).where(
                ModelRunRow.job_id == job_id, ModelRunRow.model == model
            )
        )
        return res.scalar_one_or_none()

    async def append_turn(self, job_id: str, model: str, turn: Turn) -> None:
        async with self._session() as session, session.begin():
            run_id = await self._run_id(session, job_id, model)
            if run_id is None:
                run = ModelRunRow(job_id=job_id, model=model, status="running")
                session.add(run)
                await session.flush()
                run_id = run.id
            session.add(
                TurnRow(
                    model_run_id=run_id,
                    idx=turn.index,
                    prompt=turn.prompt,
                    response=turn.response,
                    verdict=turn.verdict.value,
                    reasons={"items": turn.reasons},
                    latency_ms=turn.latency_ms,
                    error=turn.error,
                )
            )

    async def update_model_run(
        self,
        job_id: str,
        model: str,
        *,
        status: JobStatus,
        final_output: str | None,
        final_verdict: Verdict | None,
    ) -> None:
        async with self._session() as session, session.begin():
            res = await session.execute(
                select(ModelRunRow).where(
                    ModelRunRow.job_id == job_id, ModelRunRow.model == model
                )
            )
            run = res.scalar_one_or_none()
            if run is None:
                return
            run.status = status.value
            run.final_output = final_output
            run.final_verdict = final_verdict.value if final_verdict else None

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error: str | None = None,
        total_duration_ms: float | None = None,
    ) -> None:
        async with self._session() as session, session.begin():
            job = await session.get(AttackJobRow, job_id)
            if job is None:
                return
            job.status = status.value
            if error is not None:
                job.error = error
            if total_duration_ms is not None:
                job.total_duration_ms = total_duration_ms
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                from crescendo.domain.models import now_utc

                job.completed_at = now_utc()

    # ---- reads --------------------------------------------------------

    async def load_job(self, job_id: str) -> AttackJob | None:
        async with self._session() as session:
            row = await session.get(AttackJobRow, job_id)
            if row is None:
                return None
            return _row_to_domain(row)


def _row_to_domain(row: AttackJobRow) -> AttackJob:
    runs: dict[str, ModelRun] = {}
    for r in row.runs:
        turns = [
            Turn(
                index=t.idx,
                prompt=t.prompt,
                response=t.response,
                verdict=Verdict(t.verdict),
                reasons=(t.reasons or {}).get("items", []),
                latency_ms=t.latency_ms or 0.0,
                error=t.error,
            )
            for t in sorted(r.turns, key=lambda x: x.idx)
        ]
        runs[r.model] = ModelRun(
            model=r.model,
            status=JobStatus(r.status),
            turns=turns,
            final_output=r.final_output,
            final_verdict=Verdict(r.final_verdict) if r.final_verdict else None,
        )
    return AttackJob(
        id=row.id,
        objective=row.objective,
        strategy_kind=StrategyKind(row.strategy_kind),
        max_turns=row.max_turns,
        temperature=row.temperature,
        seed=row.seed,
        status=JobStatus(row.status),
        runs=runs,
        error=row.error,
        created_at=row.created_at,
        completed_at=row.completed_at,
        total_duration_ms=row.total_duration_ms,
    )
