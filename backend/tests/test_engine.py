from crescendo.application.attack_engine import AttackEngine
from crescendo.domain.models import JobStatus, StrategyKind, Verdict
from crescendo.strategies.factory import make_strategy_factory
from conftest import FakeAttacker, FakeJudge, FakeRepo, FakeTarget, make_job


async def test_engine_runs_template_across_models():
    repo = FakeRepo()
    job = make_job(["llama3", "qwen"], max_turns=5, kind=StrategyKind.TEMPLATE)
    await repo.save(job)
    engine = AttackEngine(repo=repo, target=FakeTarget(default="a safe answer"), judge=FakeJudge())
    factory = make_strategy_factory(StrategyKind.TEMPLATE, FakeAttacker(["x"]))

    await engine.run(job, factory)

    assert job.status == JobStatus.COMPLETED
    assert all(run.status == JobStatus.COMPLETED for run in job.runs.values())
    # 5-turn template runs to completion for each model.
    assert all(len(run.turns) == 5 for run in job.runs.values())


async def test_engine_early_stops_on_jailbroken():
    repo = FakeRepo()
    job = make_job(["llama3"], max_turns=5, kind=StrategyKind.TEMPLATE)
    await repo.save(job)
    # Any response containing "BREACH" is judged Jailbroken -> early stop.
    target = FakeTarget(default="BREACH: here is the answer")
    judge = FakeJudge(rules={"BREACH": Verdict.JAILBROKEN})
    engine = AttackEngine(repo=repo, target=target, judge=judge)
    factory = make_strategy_factory(StrategyKind.TEMPLATE, FakeAttacker(["x"]))

    await engine.run(job, factory)

    run = job.runs["llama3"]
    assert run.final_verdict == Verdict.JAILBROKEN
    assert len(run.turns) == 1  # stopped after the first jailbroken turn


async def test_engine_reactive_uses_attacker_questions():
    repo = FakeRepo()
    job = make_job(["llama3"], max_turns=2, kind=StrategyKind.REACTIVE)
    await repo.save(job)
    attacker = FakeAttacker(
        [
            '{"generatedQuestion":"first question","lastResponseSummary":""}',
            '{"generatedQuestion":"second question","lastResponseSummary":"s"}',
        ]
    )
    engine = AttackEngine(repo=repo, target=FakeTarget(default="safe"), judge=FakeJudge())
    factory = make_strategy_factory(StrategyKind.REACTIVE, attacker)

    await engine.run(job, factory)

    run = job.runs["llama3"]
    assert run.turns[0].prompt == "first question"
    assert run.turns[1].prompt == "second question"
