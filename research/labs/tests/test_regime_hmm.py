from __future__ import annotations
import math
import unittest

from research.labs.regime_hmm import (
    AlphaBetaHMMFilter,
    CausalHMMFilter, FeatureScaler, REGIME_HIGH_VOL, REGIME_RANGE, REGIME_TREND_UP,
    REGIME_UNDEFINED, causal_belief_update, features_from_closes,
    gaussian_log_likelihood, map_model_states, walk_forward_folds,
)


class FakeGaussianHMM:
    covariance_type = "full"
    startprob_ = [0.5, 0.3, 0.2]
    transmat_ = [[0.90, 0.08, 0.02], [0.05, 0.90, 0.05], [0.05, 0.10, 0.85]]
    means_ = [[-0.10, -0.40], [1.20, -0.10], [0.10, 1.30]]
    covars_ = [
        [[0.50, 0.0], [0.0, 0.50]],
        [[0.70, 0.0], [0.0, 0.40]],
        [[0.80, 0.0], [0.0, 0.70]],
    ]


class TestCausalBeliefUpdate(unittest.TestCase):
    def test_posterior_normalizes_and_moves_toward_likelihood(self):
        result = causal_belief_update([0.5, 0.5], [[0.9, 0.1], [0.1, 0.9]], [-4.0, -0.1])
        self.assertAlmostEqual(sum(result), 1.0, places=12)
        self.assertGreater(result[1], result[0])

    def test_rejects_bad_transition_rows(self):
        with self.assertRaises(ValueError):
            causal_belief_update([0.5, 0.5], [[0.9, 0.3], [0.1, 0.9]], [-1.0, -1.0])

    def test_rejects_non_finite_likelihoods(self):
        with self.assertRaises(ValueError):
            causal_belief_update([0.5, 0.5], [[0.9, 0.1], [0.1, 0.9]], [float("nan"), -1.0])

    def test_alpha_beta_update_uses_equal_exit_prior_and_tempered_likelihood(self):
        result = alpha_beta_belief_update([0.98, 0.01, 0.01], [-4.0, -0.1, -2.0], alpha=1/3, beta=1.0)
        expected = [math.exp(v - max([-4.0, -0.1, -2.0])) for v in [-4.0, -0.1, -2.0]]
        expected = [v / sum(expected) for v in expected]
        for actual, target in zip(result, expected):
            self.assertAlmostEqual(actual, target, places=12)

    def test_alpha_beta_rejects_out_of_range_alpha_and_bad_beta(self):
        with self.assertRaises(ValueError):
            alpha_beta_belief_update([0.5, 0.5], [-1.0, -2.0], alpha=1.01, beta=1.0)
        with self.assertRaises(ValueError):
            alpha_beta_belief_update([0.5, 0.5], [-1.0, -2.0], alpha=0.1, beta=0.0)


class TestGaussianLikelihood(unittest.TestCase):
    def test_standard_normal_at_mean(self):
        value = gaussian_log_likelihood([0.0, 0.0], [0.0, 0.0], [[1.0, 0.0], [0.0, 1.0]])
        self.assertAlmostEqual(value, -math.log(2.0 * math.pi), places=10)

    def test_rejects_non_positive_definite_covariance(self):
        with self.assertRaises(ValueError):
            gaussian_log_likelihood([0.0], [0.0], [[0.0]])


class TestMappingAndFilter(unittest.TestCase):
    def test_state_mapping_uses_parameters_not_ids(self):
        labels = map_model_states(FakeGaussianHMM())
        self.assertEqual(labels[1], REGIME_TREND_UP)
        self.assertEqual(labels[2], REGIME_HIGH_VOL)
        self.assertEqual(labels[0], REGIME_RANGE)

    def test_filter_emits_normalized_posterior(self):
        filter_ = CausalHMMFilter(FakeGaussianHMM(), [REGIME_RANGE, REGIME_TREND_UP, REGIME_HIGH_VOL])
        signal = filter_.update([1.1, -0.1])
        self.assertAlmostEqual(sum(signal.posterior), 1.0, places=12)
        self.assertIn(signal.regime, {REGIME_RANGE, REGIME_TREND_UP, REGIME_HIGH_VOL, REGIME_UNDEFINED})
        self.assertEqual(filter_.last_posterior, signal.posterior)

    def test_uncertain_filter_output_is_undefined(self):
        filter_ = CausalHMMFilter(
            FakeGaussianHMM(), [REGIME_RANGE, REGIME_TREND_UP, REGIME_HIGH_VOL], min_confidence=0.99
        )
        signal = filter_.update([0.0, 0.0])
        if signal.confidence < 0.99:
            self.assertFalse(signal.usable)
            self.assertEqual(signal.regime, REGIME_UNDEFINED)

    def test_reset_is_explicit(self):
        filter_ = CausalHMMFilter(FakeGaussianHMM(), [REGIME_RANGE, REGIME_TREND_UP, REGIME_HIGH_VOL])
        filter_.update([0.0, 0.0])
        self.assertIsNotNone(filter_.last_posterior)
        filter_.reset()
        self.assertIsNone(filter_.last_posterior)

    def test_alpha_beta_filter_uses_alpha_beta_recursion(self):
        filter_ = AlphaBetaHMMFilter(FakeGaussianHMM(), alpha=1/3, beta=0.8,
                                     labels=[REGIME_RANGE, REGIME_TREND_UP, REGIME_HIGH_VOL])
        first = filter_.update([0.0, 0.0])
        second = filter_.update([0.0, 1.1])
        self.assertAlmostEqual(sum(first.posterior), 1.0, places=12)
        self.assertAlmostEqual(sum(second.posterior), 1.0, places=12)
        self.assertNotEqual(first.posterior, second.posterior)


class TestFeaturesAndWalkForward(unittest.TestCase):
    def test_features_use_only_past_and_current_closes(self):
        closes = [100.0, 101.0, 99.0, 100.5, 102.0, 101.5, 103.0]
        earlier = features_from_closes(closes, window=3)
        mutated_future = closes[:5] + [500.0, 600.0]
        later = features_from_closes(mutated_future, window=3)
        self.assertEqual(earlier[:2], later[:2])

    def test_feature_engineering_rejects_non_positive_prices(self):
        with self.assertRaises(ValueError):
            features_from_closes([1.0, 0.0, 1.2], window=2)

    def test_walk_forward_is_chronological_and_non_overlapping(self):
        folds = walk_forward_folds(620, train_size=500, test_size=50)
        self.assertEqual(len(folds), 3)
        self.assertEqual((folds[0].train_start, folds[0].train_end), (0, 500))
        self.assertEqual((folds[0].test_start, folds[0].test_end), (500, 550))
        self.assertEqual((folds[1].train_start, folds[1].test_start), (50, 550))
        self.assertEqual(folds[-1].test_end, 620)

    def test_invalid_walk_forward_parameters_fail(self):
        with self.assertRaises(ValueError):
            walk_forward_folds(100, train_size=50, test_size=20, step_size=10)

    def test_scaler_is_deterministic_and_reuses_train_statistics(self):
        scaler = FeatureScaler.fit([(1.0, 10.0), (3.0, 14.0)])
        self.assertEqual(scaler.transform_one((2.0, 12.0)), (0.0, 0.0))
        self.assertEqual(scaler.transform_one((5.0, 18.0)), (3.0, 3.0))


if __name__ == "__main__":
    unittest.main()
