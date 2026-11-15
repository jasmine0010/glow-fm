from types import SimpleNamespace

import pytest

from hidden_floods.frozen_overbank import evaluate, trust_signal


@pytest.mark.parametrize(("confident", "rainy", "expected"), [(True, False, "green"), (True, True, "red"), (False, False, "red"), (False, True, "red")])
def test_trust_signal_is_green_only_when_confident_and_not_rainy(confident, rainy, expected):
    assert trust_signal(confident, rainy) == expected


@pytest.mark.parametrize(("river", "pair"), [("yellow", "055D_oct16"), ("satilla", "026D_oct14")])
def test_refuses_a_pass_that_is_not_listed(river, pair):
    with pytest.raises(ValueError, match="not a listed overbank pass"):
        evaluate(SimpleNamespace(name=river), pair)
