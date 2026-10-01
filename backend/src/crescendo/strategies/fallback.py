"""
Fallback strategy - responsibility chain over other strategies.

Tries each strategy in order; if one raises StrategyUnavailable before
committing, it advances to the next. Once a strategy returns a prompt, it
locks onto it for the rest of the run. This replaces the PoC's inline
gemini -> reactive -> template try/except cascade in the route handler.
"""
from __future__ import annotations

import logging

from crescendo.domain.ports import AttackContext, AttackStrategy
from crescendo.strategies.errors import StrategyUnavailable

logger = logging.getLogger(__name__)


class FallbackStrategy:
    """Implements AttackStrategy by cascading over a list of strategies."""

    def __init__(self, chain: list[AttackStrategy]) -> None:
        if not chain:
            raise ValueError("FallbackStrategy requires at least one strategy")
        self._chain = chain
        self._locked: AttackStrategy | None = None

    async def next_prompt(self, ctx: AttackContext) -> str | None:
        if self._locked is not None:
            return await self._locked.next_prompt(ctx)

        for i, strategy in enumerate(self._chain):
            try:
                prompt = await strategy.next_prompt(ctx)
            except StrategyUnavailable as e:
                logger.warning(
                    "Strategy %s unavailable (%s); cascading to next.",
                    type(strategy).__name__,
                    e,
                )
                continue
            self._locked = strategy
            return prompt
        return None
