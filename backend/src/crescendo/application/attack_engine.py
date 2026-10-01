"""
AttackEngine - the single execution loop.

Models run in parallel (asyncio.gather); turns run serially per model. One
unified loop serves all strategies (gemini/template/reactive) - the strategy
decides the next prompt, the engine handles transport, judging, persistence,
backtracking and stopping. This replaces the PoC's two near-duplicate
executors.
"""
from __future__ import annotations

import logging
import time

from crescendo.domain import services
from crescendo.domain.models import AttackJob, JobStatus, ModelRun, Turn, Verdict
from crescendo.domain.ports import (
    AttackContext,
    JobRepositoryPort,
    JudgePort,
    TargetModelPort,
)

logger = logging.getLogger(__name__)


class AttackEngine:
    def __init__(
        self,
        *,
        repo: JobRepositoryPort,
        target: TargetModelPort,
        judge: JudgePort,
    ) -> None:
        self._repo = repo
        self._target = target
        self._judge = judge

    async def run(self, job: AttackJob, strategy_factory) -> None:
        """Execute the whole job. Strategy factory yields a fresh, stateful
        strategy per model (models run concurrently)."""
        import asyncio

        start = time.time()
        await self._repo.update_job_status(job.id, JobStatus.RUNNING)
        try:
            await asyncio.gather(
                *[
                    self._run_model(job, run, strategy_factory())
                    for run in job.runs.values()
                ]
            )
            await self._repo.update_job_status(
                job.id,
                JobStatus.COMPLETED,
                total_duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Attack job %s failed", job.id)
            await self._repo.update_job_status(job.id, JobStatus.FAILED, error=str(e))

    async def _run_model(self, job: AttackJob, run: ModelRun, strategy) -> None:
        ctx = AttackContext(
            objective=job.objective, max_turns=job.max_turns, seed=job.seed
        )
        await self._repo.update_model_run(job.id, run.model, status=JobStatus.RUNNING)

        for i in range(job.max_turns):
            prompt = await strategy.next_prompt(ctx)
            if prompt is None:
                break

            result = await self._target.chat(
                run.model,
                ctx.messages + [{"role": "user", "content": prompt}],
                job.temperature,
            )
            verdict, reasons = self._judge.judge(result.text, error=result.error)
            turn = Turn(
                index=i + 1,
                prompt=prompt,
                response=result.text if result.success else None,
                verdict=verdict,
                reasons=reasons,
                latency_ms=result.latency_ms,
                error=result.error,
            )
            run.turns.append(turn)
            await self._repo.append_turn(job.id, run.model, turn)

            # Refusals are backtracked out of the target-visible history so an
            # adaptive strategy can retry from a softer angle.
            ctx.record(turn, target_visible=verdict != Verdict.REFUSAL)

            if services.should_stop(turn, max_turns_reached=(i + 1 >= job.max_turns)):
                break

        final = services.pick_final_turn(run.turns)
        any_success = any(t.success for t in run.turns)
        run.status = JobStatus.COMPLETED if any_success else JobStatus.FAILED
        run.final_output = final.response if final else None
        run.final_verdict = final.verdict if final else None

        await self._repo.update_model_run(
            job.id,
            run.model,
            status=run.status,
            final_output=run.final_output,
            final_verdict=run.final_verdict,
        )
