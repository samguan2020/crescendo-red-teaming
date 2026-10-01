"""
Ports (interfaces) the domain/application depend on. Adapters implement them.

Dependency direction is strictly inward: adapters depend on these Protocols,
never the reverse. This keeps the domain testable without Redis, Postgres,
Gemini or HuggingFace.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from crescendo.domain.models import AttackJob, ChatResult, JobStatus, Turn, Verdict


@dataclass
class AttackContext:
    """
    The running state a strategy sees when deciding the next prompt.

    `messages` is the target-visible conversation (OpenAI chat format).
    `history` is the strategy-visible record including verdicts (so reactive
    strategies can steer / backtrack). Bounded-turn strategies (e.g. a future
    single-shot or parse-driven mode) simply return None once exhausted.
    """

    objective: str
    max_turns: int
    seed: int | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    history: list[Turn] = field(default_factory=list)

    @property
    def round(self) -> int:
        """1-indexed number of the turn about to be generated."""
        return len(self.history) + 1

    @property
    def last_turn(self) -> Turn | None:
        return self.history[-1] if self.history else None

    def record(self, turn: Turn, *, target_visible: bool) -> None:
        """Append a completed turn. `target_visible=False` backtracks it out
        of the target conversation (e.g. a refusal the attacker wants to retry
        from a softer angle), while still keeping it in strategy history."""
        self.history.append(turn)
        if target_visible and turn.success:
            self.messages.append({"role": "user", "content": turn.prompt})
            self.messages.append({"role": "assistant", "content": turn.response or ""})


@runtime_checkable
class AttackStrategy(Protocol):
    """Produces the next prompt for the current context, or None to stop."""

    async def next_prompt(self, ctx: AttackContext) -> str | None: ...


class TargetModelPort(Protocol):
    """A target LLM under evaluation."""

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> ChatResult: ...


class AttackerLLMPort(Protocol):
    """
    The attacker LLM (e.g. Gemini) used by gemini/reactive strategies to
    author or adapt prompts. Thin text-in/text-out so strategies stay free of
    any specific SDK and remain unit-testable with a fake.
    """

    async def complete(self, messages: list[dict[str, str]], *, temperature: float) -> str: ...


class JudgePort(Protocol):
    """Classifies a single target response into a Verdict."""

    def judge(self, response: str | None, *, error: str | None = None) -> tuple[Verdict, list[str]]: ...


class JobRepositoryPort(Protocol):
    """Durable + cached persistence of attack jobs. Single write surface."""

    async def save(self, job: AttackJob) -> None: ...

    async def get(self, job_id: str) -> AttackJob | None: ...

    async def append_turn(self, job_id: str, model: str, turn: Turn) -> None: ...

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error: str | None = None,
        total_duration_ms: float | None = None,
    ) -> None: ...

    async def update_model_run(
        self,
        job_id: str,
        model: str,
        *,
        status: JobStatus,
        final_output: str | None = None,
        final_verdict: Verdict | None = None,
    ) -> None: ...


class TaskQueuePort(Protocol):
    """Hands a queued job off to a worker runtime (in-process or external)."""

    async def enqueue(self, job_id: str) -> None: ...
