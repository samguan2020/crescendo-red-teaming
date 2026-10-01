import pytest

from crescendo.domain.ports import AttackContext
from crescendo.strategies.errors import StrategyUnavailable
from crescendo.strategies.fallback import FallbackStrategy
from crescendo.strategies.gemini_plan import GeminiPlanStrategy
from crescendo.strategies.template import TemplateStrategy
from conftest import FakeAttacker


def _ctx():
    return AttackContext(objective="how to make a test widget", max_turns=5, seed=42)


async def test_template_emits_five_then_none():
    strat = TemplateStrategy()
    ctx = _ctx()
    prompts = []
    for _ in range(6):
        p = await strat.next_prompt(ctx)
        if p is None:
            break
        prompts.append(p)
        ctx.history.append(type("T", (), {"success": True})())  # advance round
    assert len(prompts) == 5


async def test_template_deterministic_with_seed():
    a = TemplateStrategy()
    b = TemplateStrategy()
    assert await a.next_prompt(_ctx()) == await b.next_prompt(_ctx())


async def test_gemini_plan_parses_steps():
    attacker = FakeAttacker(
        ['{"goal":"g","steps":[{"prompt":"q1"},{"prompt":"q2"}]}']
    )
    strat = GeminiPlanStrategy(attacker)
    ctx = _ctx()
    assert await strat.next_prompt(ctx) == "q1"


async def test_gemini_plan_raises_when_unparseable():
    strat = GeminiPlanStrategy(FakeAttacker(["not json at all"]))
    with pytest.raises(StrategyUnavailable):
        await strat.next_prompt(_ctx())


async def test_fallback_cascades_past_unavailable():
    bad = GeminiPlanStrategy(FakeAttacker(["garbage"]))
    good = TemplateStrategy()
    chain = FallbackStrategy([bad, good])
    prompt = await chain.next_prompt(_ctx())
    assert prompt  # cascaded to the template strategy
