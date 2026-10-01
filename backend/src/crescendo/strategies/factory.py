"""
Strategy factory - maps a StrategyKind to a fresh AttackStrategy.

Returns a *factory callable* (not a shared instance) because strategies are
stateful per model run (they cache the generated plan / attacker memory), and
the engine runs models in parallel.

Extension points (not built yet, see Transform-Run-Iterative analysis):
- SingleShotStrategy(max_turns=1)  -> reproduces the old "Run" feature.
- ParseDerivedStrategy             -> reproduces the old "Iterative" feature
  (next prompt parsed from the target's previous response).
Both would slot in here with no change to the engine or domain.
"""
from __future__ import annotations

from typing import Callable

from crescendo.domain.models import StrategyKind
from crescendo.domain.ports import AttackerLLMPort, AttackStrategy
from crescendo.strategies.fallback import FallbackStrategy
from crescendo.strategies.gemini_plan import GeminiPlanStrategy
from crescendo.strategies.reactive import ReactiveStrategy
from crescendo.strategies.template import TemplateStrategy

StrategyFactory = Callable[[], AttackStrategy]


def make_strategy_factory(
    kind: StrategyKind,
    attacker: AttackerLLMPort,
) -> StrategyFactory:
    """Build a per-run strategy factory for the requested kind.

    `gemini` is a cascade gemini -> reactive -> template, mirroring the PoC's
    default resilience (an attacker refusal never 500s the request).
    """

    def factory() -> AttackStrategy:
        if kind == StrategyKind.TEMPLATE:
            return TemplateStrategy()
        if kind == StrategyKind.REACTIVE:
            return ReactiveStrategy(attacker)
        # GEMINI: resilient cascade.
        return FallbackStrategy(
            [
                GeminiPlanStrategy(attacker),
                ReactiveStrategy(attacker),
                TemplateStrategy(),
            ]
        )

    return factory
