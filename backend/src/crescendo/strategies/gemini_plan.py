"""
Gemini one-shot plan strategy.

On the first call it asks the attacker LLM for a complete multi-step plan
(JSON), then serves one prompt per round by index. If the LLM output can't be
parsed into a usable plan, it raises StrategyUnavailable so the fallback chain
can cascade to the next strategy.
"""
from __future__ import annotations

from crescendo.domain.ports import AttackContext, AttackerLLMPort
from crescendo.strategies.errors import StrategyUnavailable
from crescendo.strategies.parsing import extract_json_object
from crescendo.strategies.prompts import CRESCENDO_GUIDELINE, PLAN_GENERATION_PROMPT


class GeminiPlanStrategy:
    """LLM-authored static plan. Implements AttackStrategy."""

    def __init__(self, attacker: AttackerLLMPort, *, temperature: float = 0.3) -> None:
        self._attacker = attacker
        self._temperature = temperature
        self._prompts: list[str] | None = None

    async def _generate_plan(self, objective: str) -> list[str]:
        prompt = PLAN_GENERATION_PROMPT.format(
            user_objective=objective,
            crescendo_guideline=CRESCENDO_GUIDELINE,
        )
        text = await self._attacker.complete(
            [{"role": "user", "content": prompt}],
            temperature=self._temperature,
        )
        data = extract_json_object(text)
        if not data or not isinstance(data.get("steps"), list) or not data["steps"]:
            raise StrategyUnavailable("Gemini plan unparseable or empty")
        prompts = [
            str(s["prompt"]).strip()
            for s in data["steps"]
            if isinstance(s, dict) and s.get("prompt")
        ]
        if not prompts:
            raise StrategyUnavailable("Gemini plan had no usable prompts")
        return prompts

    async def next_prompt(self, ctx: AttackContext) -> str | None:
        if self._prompts is None:
            self._prompts = await self._generate_plan(ctx.objective)
        idx = ctx.round - 1
        if idx >= len(self._prompts):
            return None
        return self._prompts[idx]
