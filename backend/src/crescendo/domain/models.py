"""
Domain model - pure Python, zero framework dependencies.

The whole system reduces to: given an `objective` and a set of target
`models`, an `AttackStrategy` produces a sequence of escalating prompts; each
prompt is sent to a model, the reply is judged into a `Verdict`, and the
ordered `Turn`s form an auditable attack trace per `ModelRun`. The aggregate
root is `AttackJob`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Verdict(str, Enum):
    """Safety classification of a single target response."""

    REFUSAL = "refusal"
    COMPLIANT = "compliant"
    NEAR_MISS = "near_miss"
    JAILBROKEN = "jailbroken"
    ERROR = "error"


class StrategyKind(str, Enum):
    """How the multi-turn prompts are produced."""

    GEMINI = "gemini"
    TEMPLATE = "template"
    REACTIVE = "reactive"


@dataclass
class Turn:
    """One prompt -> response -> verdict interaction."""

    index: int
    prompt: str
    response: str | None = None
    verdict: Verdict = Verdict.ERROR
    reasons: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.response)


@dataclass
class ModelRun:
    """All turns executed against one target model."""

    model: str
    status: JobStatus = JobStatus.QUEUED
    turns: list[Turn] = field(default_factory=list)
    final_output: str | None = None
    final_verdict: Verdict | None = None

    @property
    def current_step(self) -> int:
        return len(self.turns)


@dataclass
class AttackJob:
    """Aggregate root: one evaluation submission across N models."""

    id: str
    objective: str
    strategy_kind: StrategyKind
    max_turns: int
    temperature: float = 0.7
    seed: int | None = None
    status: JobStatus = JobStatus.QUEUED
    runs: dict[str, ModelRun] = field(default_factory=dict)
    error: str | None = None
    created_at: datetime = field(default_factory=now_utc)
    completed_at: datetime | None = None
    total_duration_ms: float | None = None

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        objective: str,
        models: list[str],
        strategy_kind: StrategyKind,
        max_turns: int,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> "AttackJob":
        return cls(
            id=job_id,
            objective=objective,
            strategy_kind=strategy_kind,
            max_turns=max_turns,
            temperature=temperature,
            seed=seed,
            runs={m: ModelRun(model=m) for m in models},
        )

    @property
    def models(self) -> list[str]:
        return list(self.runs.keys())


@dataclass
class ChatResult:
    """Outcome of a single target-model chat call (port-level value object)."""

    text: str | None
    latency_ms: float
    success: bool
    error: str | None = None


@dataclass
class JudgeResult:
    verdict: Verdict
    reasons: list[str]
