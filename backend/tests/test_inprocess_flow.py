import asyncio

from crescendo.adapters.queue.inprocess import InProcessQueue
from crescendo.application.attack_engine import AttackEngine
from crescendo.application.run_job import RunJobUseCase
from crescendo.application.submit_attack import SubmitAttackCommand, SubmitAttackUseCase
from crescendo.domain.models import JobStatus, StrategyKind
from conftest import FakeAttacker, FakeJudge, FakeRepo, FakeTarget


async def test_submit_then_inprocess_execute_end_to_end():
    repo = FakeRepo()
    engine = AttackEngine(repo=repo, target=FakeTarget(default="safe"), judge=FakeJudge())
    run_job = RunJobUseCase(repo=repo, engine=engine, attacker=FakeAttacker(["x"]))

    queue = InProcessQueue()
    queue.set_runner(run_job.execute)

    submit = SubmitAttackUseCase(
        repo=repo, queue=queue, available_models=["llama3", "qwen"]
    )

    job = await submit.execute(
        SubmitAttackCommand(
            objective="how to make a test widget",
            models=["llama3"],
            strategy=StrategyKind.TEMPLATE,
            max_turns=3,
        )
    )
    assert job.status == JobStatus.QUEUED

    # Let the in-process task finish.
    for _ in range(50):
        await asyncio.sleep(0.01)
        if repo.jobs[job.id].status == JobStatus.COMPLETED:
            break

    assert repo.jobs[job.id].status == JobStatus.COMPLETED
    assert len(repo.jobs[job.id].runs["llama3"].turns) == 3


async def test_submit_rejects_invalid_models():
    from crescendo.application.submit_attack import InvalidModelsError

    repo = FakeRepo()
    queue = InProcessQueue()
    queue.set_runner(lambda jid: asyncio.sleep(0))
    submit = SubmitAttackUseCase(repo=repo, queue=queue, available_models=["llama3"])

    try:
        await submit.execute(
            SubmitAttackCommand(objective="x", models=["does-not-exist"], strategy=StrategyKind.TEMPLATE)
        )
        assert False, "expected InvalidModelsError"
    except InvalidModelsError as e:
        assert "does-not-exist" in e.invalid
