"""Test fakes for the domain ports - no external services required."""
from __future__ import annotations

from crescendo.domain.models import (
    AttackJob,
    ChatResult,
    JobStatus,
    StrategyKind,
    Turn,
    Verdict,
)


class FakeRepo:
    """In-memory JobRepositoryPort."""

    def __init__(self) -> None:
        self.jobs: dict[str, AttackJob] = {}
        self.appended: list[tuple[str, str, Turn]] = []

    async def save(self, job: AttackJob) -> None:
        self.jobs[job.id] = job

    async def get(self, job_id: str) -> AttackJob | None:
        return self.jobs.get(job_id)

    async def append_turn(self, job_id: str, model: str, turn: Turn) -> None:
        self.appended.append((job_id, model, turn))

    async def update_job_status(self, job_id, status, *, error=None, total_duration_ms=None):
        job = self.jobs[job_id]
        job.status = status
        job.error = error
        if total_duration_ms is not None:
            job.total_duration_ms = total_duration_ms

    async def update_model_run(self, job_id, model, *, status, final_output=None, final_verdict=None):
        run = self.jobs[job_id].runs[model]
        run.status = status
        run.final_output = final_output
        run.final_verdict = final_verdict


class FakeTarget:
    """TargetModelPort that maps the latest user prompt to a scripted reply."""

    def __init__(self, replies: dict[str, str] | None = None, default: str = "ok") -> None:
        self._replies = replies or {}
        self._default = default

    async def chat(self, model, messages, temperature) -> ChatResult:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        for key, reply in self._replies.items():
            if key in last_user:
                return ChatResult(text=reply, latency_ms=1.0, success=True)
        return ChatResult(text=self._default, latency_ms=1.0, success=True)


class FakeJudge:
    """JudgePort driven by simple substring rules over the response."""

    def __init__(self, rules: dict[str, Verdict] | None = None) -> None:
        self._rules = rules or {}

    def judge(self, response, *, error=None):
        if error:
            return Verdict.ERROR, ["error"]
        text = response or ""
        for key, verdict in self._rules.items():
            if key in text:
                return verdict, [f"matched {key}"]
        return Verdict.COMPLIANT, ["default"]


class FakeAttacker:
    """AttackerLLMPort returning scripted completions in order."""

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = outputs
        self.calls = 0

    async def complete(self, messages, *, temperature) -> str:
        out = self._outputs[min(self.calls, len(self._outputs) - 1)]
        self.calls += 1
        return out


def make_job(models: list[str], *, max_turns: int = 5, kind=StrategyKind.TEMPLATE) -> AttackJob:
    return AttackJob.create(
        job_id="job-1",
        objective="how to make a test widget",
        models=models,
        strategy_kind=kind,
        max_turns=max_turns,
    )
