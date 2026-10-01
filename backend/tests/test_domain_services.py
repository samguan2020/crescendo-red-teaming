from crescendo.domain.models import Turn, Verdict
from crescendo.domain.services import pick_final_turn, should_stop


def _turn(idx, verdict, *, response="x", error=None):
    return Turn(index=idx, prompt="p", response=response, verdict=verdict, error=error)


def test_should_stop_on_error():
    assert should_stop(_turn(1, Verdict.ERROR, response=None, error="boom"), max_turns_reached=False)


def test_should_stop_on_jailbroken():
    assert should_stop(_turn(1, Verdict.JAILBROKEN), max_turns_reached=False)


def test_should_continue_when_compliant_and_turns_left():
    assert not should_stop(_turn(1, Verdict.COMPLIANT), max_turns_reached=False)


def test_should_stop_when_turn_cap_reached():
    assert should_stop(_turn(3, Verdict.COMPLIANT), max_turns_reached=True)


def test_pick_final_prefers_jailbroken_then_latest():
    turns = [
        _turn(1, Verdict.COMPLIANT),
        _turn(2, Verdict.JAILBROKEN),
        _turn(3, Verdict.NEAR_MISS),
    ]
    final = pick_final_turn(turns)
    assert final.index == 2
    assert final.verdict == Verdict.JAILBROKEN


def test_pick_final_none_when_no_success():
    turns = [_turn(1, Verdict.ERROR, response=None, error="e")]
    assert pick_final_turn(turns) is None
