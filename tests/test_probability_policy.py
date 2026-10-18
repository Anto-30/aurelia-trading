from math import inf, nan

from runtime.core.authority import MAX_PROBABILITY, MIN_PROBABILITY, probability_is_valid


def test_probability_policy_constants_are_exact():
    assert MIN_PROBABILITY == 0.55
    assert MAX_PROBABILITY == 0.75


def test_probability_policy_includes_both_boundaries():
    assert probability_is_valid(0.55)
    assert probability_is_valid(0.75)


def test_probability_policy_rejects_values_outside_band_without_clipping():
    for probability in (0.549999, 0.750001, 0.82, -0.1, 1.01):
        assert not probability_is_valid(probability)


def test_probability_policy_rejects_malformed_and_non_finite_values():
    for probability in (True, False, "0.6", None, nan, inf, -inf):
        assert not probability_is_valid(probability)
