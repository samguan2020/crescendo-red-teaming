"""
Redis projection - read model for fast polling. Rebuildable from Postgres.

Sharded layout so parallel per-model writes never collide:
    job:{id}:meta            - job scalars + model list
    job:{id}:model:{model}   - one run's status + turns
"""
from __future__ import annotations

from crescendo.adapters.persistence.redis_client import BaseRedisClient
from crescendo.domain.models import (
    AttackJob,
    JobStatus,
    ModelRun,
    StrategyKind,
    Turn,
    Verdict,
)


def _meta_key(job_id: str) -> str:
    return f"job:{job_id}:meta"


def _model_key(job_id: str, model: str) -> str:
    return f"job:{job_id}:model:{model}"


def _turn_to_dict(t: Turn) -> dict:
    return {
        "index": t.index,
        "prompt": t.prompt,
        "response": t.response,
        "verdict": t.verdict.value,
        "reasons": t.reasons,
        "latency_ms": t.latency_ms,
        "error": t.error,
    }


def _dict_to_turn(d: dict) -> Turn:
    return Turn(
        index=d["index"],
        prompt=d["prompt"],
        response=d.get("response"),
        verdict=Verdict(d.get("verdict", Verdict.ERROR.value)),
        reasons=d.get("reasons", []),
        latency_ms=d.get("latency_ms", 0.0),
        error=d.get("error"),
    )


class RedisJobProjection:
    def __init__(self, client: BaseRedisClient, *, ttl: int) -> None:
        self._client = client
        self._ttl = ttl

    async def init_job(self, job: AttackJob) -> None:
        await self._client.set_json(
            _meta_key(job.id),
            {
                "id": job.id,
                "objective": job.objective,
                "strategy_kind": job.strategy_kind.value,
                "max_turns": job.max_turns,
                "status": job.status.value,
                "models": job.models,
                "error": job.error,
                "total_duration_ms": job.total_duration_ms,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            },
            ttl=self._ttl,
        )
        for model, run in job.runs.items():
            await self._write_run(job.id, run)

    async def _write_run(self, job_id: str, run: ModelRun) -> None:
        await self._client.set_json(
            _model_key(job_id, run.model),
            {
                "model": run.model,
                "status": run.status.value,
                "current_step": run.current_step,
                "turns": [_turn_to_dict(t) for t in run.turns],
                "final_output": run.final_output,
                "final_verdict": run.final_verdict.value if run.final_verdict else None,
            },
            ttl=self._ttl,
        )

    async def append_turn(self, job_id: str, model: str, turn: Turn) -> None:
        key = _model_key(job_id, model)
        cur = await self._client.get_json(key) or {"model": model, "turns": []}
        cur["turns"].append(_turn_to_dict(turn))
        cur["current_step"] = len(cur["turns"])
        cur["status"] = JobStatus.RUNNING.value
        await self._client.set_json(key, cur, ttl=self._ttl)

    async def patch_run(self, job_id: str, model: str, patch: dict) -> None:
        key = _model_key(job_id, model)
        cur = await self._client.get_json(key) or {"model": model, "turns": []}
        cur.update(patch)
        await self._client.set_json(key, cur, ttl=self._ttl)

    async def patch_meta(self, job_id: str, patch: dict) -> None:
        cur = await self._client.get_json(_meta_key(job_id)) or {}
        cur.update(patch)
        await self._client.set_json(_meta_key(job_id), cur, ttl=self._ttl)

    async def get_job(self, job_id: str) -> AttackJob | None:
        meta = await self._client.get_json(_meta_key(job_id))
        if not meta:
            return None
        runs: dict[str, ModelRun] = {}
        for model in meta.get("models", []):
            data = await self._client.get_json(_model_key(job_id, model)) or {}
            runs[model] = ModelRun(
                model=model,
                status=JobStatus(data.get("status", JobStatus.QUEUED.value)),
                turns=[_dict_to_turn(t) for t in data.get("turns", [])],
                final_output=data.get("final_output"),
                final_verdict=(
                    Verdict(data["final_verdict"]) if data.get("final_verdict") else None
                ),
            )
        from datetime import datetime

        return AttackJob(
            id=meta["id"],
            objective=meta["objective"],
            strategy_kind=StrategyKind(meta["strategy_kind"]),
            max_turns=meta["max_turns"],
            status=JobStatus(meta["status"]),
            runs=runs,
            error=meta.get("error"),
            total_duration_ms=meta.get("total_duration_ms"),
            created_at=datetime.fromisoformat(meta["created_at"]),
            completed_at=(
                datetime.fromisoformat(meta["completed_at"])
                if meta.get("completed_at")
                else None
            ),
        )
