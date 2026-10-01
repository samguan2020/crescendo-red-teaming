"""
FastAPI routes - thin: validate via DTO, call a use case, map to DTO. No
business logic, no try/except (global handlers cover errors).
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from crescendo.adapters.inbound.http.dto import (
    AttackJobDTO,
    ModelInfo,
    ModelsResponse,
    SubmitAttackRequest,
    SubmitAttackResponse,
    job_to_dto,
)
from crescendo.application.submit_attack import SubmitAttackCommand
from crescendo.infra.container import Container

router = APIRouter()


def _container(request: Request) -> Container:
    return request.app.state.container


@router.post("/attacks", response_model=SubmitAttackResponse, status_code=202)
async def submit_attack(payload: SubmitAttackRequest, request: Request):
    container = _container(request)
    job = await container.submit_attack.execute(
        SubmitAttackCommand(
            objective=payload.objective,
            models=payload.models,
            strategy=payload.strategy,
            temperature=payload.temperature,
            max_turns=payload.max_turns,
            seed=payload.seed,
        )
    )
    return SubmitAttackResponse(
        job_id=job.id,
        status=job.status.value,
        objective=job.objective,
        strategy=job.strategy_kind.value,
        models=job.models,
        max_turns=job.max_turns,
    )


@router.get("/attacks/{job_id}", response_model=AttackJobDTO)
async def get_attack(job_id: str, request: Request):
    container = _container(request)
    job = await container.query_attack.get(job_id)
    return job_to_dto(job)


@router.get("/attacks/{job_id}/trace", response_model=AttackJobDTO)
async def get_attack_trace(job_id: str, request: Request):
    """Durable trace straight from Postgres (audit/export)."""
    container = _container(request)
    job = await container.store.load_job(job_id)
    if job is None:
        from crescendo.application.query_attack import JobNotFoundError

        raise JobNotFoundError(job_id)
    return job_to_dto(job)


@router.get("/models", response_model=ModelsResponse)
async def list_models(request: Request):
    settings = _container(request).settings
    return ModelsResponse(
        models=[
            ModelInfo(id=m, huggingface_id=settings.HUGGINGFACE_MODELS.get(m, m))
            for m in settings.AVAILABLE_MODELS
        ]
    )
