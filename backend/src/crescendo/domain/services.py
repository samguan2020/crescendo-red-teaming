"""
Pure domain services - business rules with no I/O. Unit-testable in isolation.
"""
from __future__ import annotations

from crescendo.domain.models import Turn, Verdict

# Lower number = "more jailbroken" = preferred as the run's representative.
_VERDICT_PRIORITY: dict[Verdict, int] = {
    Verdict.JAILBROKEN: 0,
    Verdict.NEAR_MISS: 1,
    Verdict.COMPLIANT: 2,
    Verdict.REFUSAL: 3,
    Verdict.ERROR: 4,
}


def should_stop(turn: Turn, *, max_turns_reached: bool) -> bool:
    """
    Decide whether to end a model's sequence after this turn.

    - Hard upstream failure: stop (don't burn turns against a dead model).
    - Jailbroken: stop early (we got what we came for).
    - Otherwise continue until the strategy or turn cap ends it.
    """
    if not turn.success:
        return True
    if turn.verdict == Verdict.JAILBROKEN:
        return True
    return max_turns_reached


def pick_final_turn(turns: list[Turn]) -> Turn | None:
    """
    Choose the representative turn for a model run: the most-jailbroken
    successful turn, breaking ties toward the later turn.
    """
    good = [t for t in turns if t.success]
    if not good:
        return None
    return min(
        good,
        key=lambda t: (_VERDICT_PRIORITY.get(t.verdict, 5), -t.index),
    )
