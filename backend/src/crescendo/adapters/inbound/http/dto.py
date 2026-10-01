"""
HTTP DTOs - request/response schemas. Kept separate from the domain model so
the wire contract can evolve independently. Mapping helpers live here too.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from crescendo.domain.models import AttackJob, StrategyKind


class SubmitAttackRequest(BaseModel):
    objective: str = Field(..., min_length=1, description="The jailbreak objective")
    models: list[str] = Field(..., min_length=1, description="Target model short names")
    strategy: StrategyKind = Field(
        default=StrategyKind.GEMINI,
        description="gemini (resilient cascade) | template (no LLM) | reactive (adaptive)",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_turns: int = Field(default=10, ge=2, le=20)
    seed: int | None = Field(default=None, description="Deterministic seed for template")


class SubmitAttackResponse(BaseModel):
    job_id: str
    status: str
    objective: str
    strategy: str
    models: list[str]
    max_turns: int


class TurnDTO(BaseModel):
    index: int
    prompt: str
    response: str | None
    verdict: str
    reasons: list[str]
    latency_ms: float
    error: str | None


class ModelRunDTO(BaseModel):
    model: str
    status: str
    current_step: int
    turns: list[TurnDTO]
    final_output: str | None
    final_verdict: str | None


class AttackJobDTO(BaseModel):
    job_id: str
    objective: str
    strategy: str
    status: str
    max_turns: int
    models: dict[str, ModelRunDTO]
    error: str | None = None
    total_duration_ms: float | None = None


class ModelInfo(BaseModel):
    id: str
    huggingface_id: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]


def job_to_dto(job: AttackJob) -> AttackJobDTO:
    return AttackJobDTO(
        job_id=job.id,
        objective=job.objective,
        strategy=job.strategy_kind.value,
        status=job.status.value,
        max_turns=job.max_turns,
        error=job.error,
        total_duration_ms=job.total_duration_ms,
        models={
            name: ModelRunDTO(
                model=run.model,
                status=run.status.value,
                current_step=run.current_step,
                turns=[
                    TurnDTO(
                        index=t.index,
                        prompt=t.prompt,
                        response=t.response,
                        verdict=t.verdict.value,
                        reasons=t.reasons,
                        latency_ms=t.latency_ms,
                        error=t.error,
                    )
                    for t in run.turns
                ],
                final_output=run.final_output,
                final_verdict=run.final_verdict.value if run.final_verdict else None,
            )
            for name, run in job.runs.items()
        },
    )
