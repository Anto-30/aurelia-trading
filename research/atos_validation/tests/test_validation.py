import math
import unittest
import numpy as np
import pandas as pd
from research.atos_validation.regime_validation import (
    _metrics, atr_position_size, chronological_partition, rolling_wfa, validate_expectancy
)
from research.atos_validation.four_model_backtest import evaluate, evaluate_fold_metrics
import tempfile, os

class ValidationTests(unittest.TestCase):
    def test_empty_return_metrics_have_six_fields(self):
        metrics = _metrics(np.asarray([], dtype=float))
        self.assertEqual(len(metrics), 6)
        self.assertTrue(all(math.isnan(value) for value in metrics))

    def test_atr_size_keeps_risk_budget_and_caps_units(self):
        a=atr_position_size(10000,.01,2,2,1,1000)
        b=atr_position_size(10000,.01,4,2,1,1000)
        self.assertAlmostEqual(a,25)
        self.assertAlmostEqual(b,12.5)
        self.assertEqual(atr_position_size(10000,.01,2,2,1,10),10)
    def test_alpha_beta_smoothing_stays_in_probability_simplex(self):
        from research.atos_validation.regime_validation import RegimeDetector
        self.assertEqual(RegimeDetector(filter_kind="alpha_beta", alpha=1/3).alpha, 1/3)
        with self.assertRaises(ValueError):
            RegimeDetector(filter_kind="alpha_beta", alpha=.34)

    def test_hmm_emissions_are_causal_and_normalize_posterior(self):
        from types import SimpleNamespace
        from research.atos_validation.regime_validation import RegimeDetector
        detector = RegimeDetector(min_confidence=0.01, max_entropy=1.0)
        detector.mean = np.array([0.0, 0.0])
        detector.scale = np.array([1.0, 1.0])
        detector.state_names = {0: "RANGE", 1: "TREND", 2: "HIGH_VOL_CHOP"}
        detector.model = SimpleNamespace(
            means_=np.array([[0.0, 0.0], [1.0, 1.0], [-1.0, -1.0]]),
            covars_=np.array([np.eye(2), np.eye(2), np.eye(2)]),
            startprob_=np.array([1.0 / 3.0] * 3),
            transmat_=np.eye(3),
        )
        prediction = detector.update([0.0, 0.0])
        self.assertEqual(len(prediction.probabilities), 3)
        self.assertTrue(prediction.valid)
        self.assertAlmostEqual(sum(prediction.probabilities), 1.0, places=12)

    def test_hmm_invalid_covariance_returns_undefined_not_a_signal(self):
        from types import SimpleNamespace
        from research.atos_validation.regime_validation import RegimeDetector
        detector = RegimeDetector(min_confidence=0.01, max_entropy=1.0)
        detector.mean = np.array([0.0, 0.0])
        detector.scale = np.array([1.0, 1.0])
        detector.state_names = {0: "RANGE", 1: "TREND", 2: "HIGH_VOL_CHOP"}
        detector.model = SimpleNamespace(
            means_=np.zeros((3, 2)),
            covars_=np.array([np.eye(2), np.diag([1.0, -1.0]), np.eye(2)]),
            startprob_=np.array([1.0 / 3.0] * 3),
            transmat_=np.eye(3),
        )
        prediction = detector.update([0.0, 0.0])
        self.assertFalse(prediction.valid)
        self.assertEqual(prediction.regime, "UNDEFINED")

    def test_bad_risk_inputs_rejected(self):
        with self.assertRaises(ValueError): atr_position_size(1000,.5,1,2,1,100)
    def test_wfa_chronological(self):
        folds=rolling_wfa(1000,train_fraction=.7,min_train=100,test_size=50)
        self.assertEqual(folds[0],(0,700,700,750))
        self.assertTrue(all(a<=b and b==c and c<d for a,b,c,d in folds))
    def test_sealed_three_month_partition(self):
        dates=pd.date_range("2024-01-01",periods=500,freq="D",tz="UTC")
        dev,sealed,cutoff=chronological_partition(dates,3)
        self.assertTrue((dates[dev[-1]]<cutoff).item() if hasattr(dates[dev[-1]]<cutoff,"item") else dates[dev[-1]]<cutoff)
        self.assertTrue((dates[sealed[0]]>=cutoff).item() if hasattr(dates[sealed[0]]>=cutoff,"item") else dates[sealed[0]]>=cutoff)

    def test_invalid_sealed_oos_month_count_rejected(self):
        dates = pd.date_range("2024-01-01", periods=500, freq="D", tz="UTC")
        with self.assertRaisesRegex(ValueError, "final_oos_months must be an integer"):
            chronological_partition(dates, 0)

    def test_invalid_hmm_feature_window_rejected(self):
        from research.atos_validation.regime_validation import RegimeDetector
        with self.assertRaisesRegex(ValueError, "window must be an integer"):
            RegimeDetector.features(np.linspace(100.0, 150.0, 50), window=1)
    def test_degradation_triggers_fallback_not_overfit_proof(self):
        ins=[.3]*200; oos=[.1]*100
        r=validate_expectancy(ins,oos,[oos[:50],oos[50:]],degradation_limit=.2,min_oos_trades=50)
        self.assertTrue(r.overfit_flag)
        self.assertEqual(r.decision,"REJECT_OR_FALLBACK")
    def test_nonpositive_insample_does_not_use_degradation_ratio(self):
        oos=[.1,.2]*50
        r=validate_expectancy([-.1,.1]*100,oos,[oos[:50],oos[50:]],min_oos_trades=50)
        self.assertIsNone(r.degradation_pct)
    def test_four_model_comparison_outputs_fold_level_metrics(self):
        models=["alpha_beta_hmm","gaussian_hmm","ma_control","unfiltered_msnr"]
        rows=[]
        for model in models:
            for i in range(4):
                rows.append({"timestamp":f"2024-01-0{i+1}T00:00:00Z","strategy":model,
                             "r_gross":.2 if i % 2 == 0 else -.1,"cost_r":.01,"fold":i // 2})
        with tempfile.NamedTemporaryFile(mode="w",suffix=".csv",delete=False) as f:
            pd.DataFrame(rows).to_csv(f.name,index=False); name=f.name
        try:
            result=evaluate_fold_metrics(name)
            self.assertEqual(len(result),8)
            self.assertEqual(result.groupby("model").size().tolist(),[2,2,2,2])
        finally:
            os.unlink(name)

    def test_four_model_ledger_rejects_negative_costs(self):
        models=["alpha_beta_hmm","gaussian_hmm","ma_control","unfiltered_msnr"]
        rows=[{"timestamp":"2024-01-01T00:00:00Z","strategy":model,
               "r_gross":.2,"cost_r":-.01,"fold":0} for model in models]
        with tempfile.NamedTemporaryFile(mode="w",suffix=".csv",delete=False) as f:
            pd.DataFrame(rows).to_csv(f.name,index=False); name=f.name
        try:
            with self.assertRaisesRegex(ValueError,"nonnegative"):
                evaluate(name)
        finally:
            os.unlink(name)

    def test_four_model_ledger_rejects_naive_timestamps(self):
        models=["alpha_beta_hmm","gaussian_hmm","ma_control","unfiltered_msnr"]
        rows=[{"timestamp":"2024-01-01T00:00:00","strategy":model,
               "r_gross":.2,"cost_r":.01,"fold":0} for model in models]
        with tempfile.NamedTemporaryFile(mode="w",suffix=".csv",delete=False) as f:
            pd.DataFrame(rows).to_csv(f.name,index=False); name=f.name
        try:
            with self.assertRaisesRegex(ValueError,"explicit timezone"):
                evaluate(name)
        finally:
            os.unlink(name)

    def test_four_model_ledger_rejects_mismatched_fold_sets(self):
        models=["alpha_beta_hmm","gaussian_hmm","ma_control","unfiltered_msnr"]
        rows=[{"timestamp":"2024-01-01T00:00:00Z","strategy":model,
               "r_gross":.2,"cost_r":.01,"fold":0} for model in models]
        rows.append({"timestamp":"2024-01-02T00:00:00Z","strategy":"alpha_beta_hmm",
                     "r_gross":.2,"cost_r":.01,"fold":1})
        with tempfile.NamedTemporaryFile(mode="w",suffix=".csv",delete=False) as f:
            pd.DataFrame(rows).to_csv(f.name,index=False); name=f.name
        try:
            with self.assertRaisesRegex(ValueError,"same WFA folds"):
                evaluate(name)
        finally:
            os.unlink(name)

    def test_four_model_comparison_needs_all_models(self):
        models=["alpha_beta_hmm","gaussian_hmm","ma_control","unfiltered_msnr"]
        rows=[]
        for m in models:
            for i in range(4):
                rows.append({"timestamp":f"2024-01-0{i+1}T00:00:00Z","strategy":m,"r_gross":.2 if i%2==0 else -.1,"cost_r":.01,"fold":i//2})
        with tempfile.NamedTemporaryFile(mode="w",suffix=".csv",delete=False) as f:
            pd.DataFrame(rows).to_csv(f.name,index=False); name=f.name
        try:
            result=evaluate(name)
            self.assertEqual(list(result.model),models)
            self.assertEqual(result.sample_size.tolist(),[4]*4)
            self.assertAlmostEqual(result.expectancy_r.iloc[0],.04)
        finally: os.unlink(name)

    def test_expectancy_rejects_nonfinite_walk_forward_fold(self):
        with self.assertRaisesRegex(ValueError, "WFA fold returns must be finite"):
            validate_expectancy(
                [.1, .2] * 100,
                [.1, .2] * 60,
                [[.1, .2], [.1, float("nan")]],
                min_oos_trades=50,
            )

    def test_expectancy_requires_two_valid_walk_forward_folds(self):
        result = validate_expectancy(
            [.1, .2] * 100,
            [.1, .2] * 60,
            [[.1, .2] * 60],
            min_oos_trades=50,
        )
        self.assertTrue(result.overfit_flag)
        self.assertEqual(result.decision, "REJECT_OR_FALLBACK")
    
    def test_expectancy_rejects_fold_returns_not_matching_oos(self):
        with self.assertRaisesRegex(ValueError, "exactly partition OOS returns"):
            validate_expectancy(
                [.1, .2] * 100,
                [.1, .2] * 50,
                [[.1, .2] * 25, [.3, .4]],
                min_oos_trades=50,
            )

if __name__=="__main__": unittest.main()
