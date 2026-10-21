import math
import unittest
import numpy as np
import pandas as pd
from research.atos_validation.regime_validation import (
    atr_position_size, chronological_partition, rolling_wfa, validate_expectancy
)
from research.atos_validation.four_model_backtest import evaluate
import tempfile, os

class ValidationTests(unittest.TestCase):
    def test_atr_size_keeps_risk_budget_and_caps_units(self):
        a=atr_position_size(10000,.01,2,2,1,1000)
        b=atr_position_size(10000,.01,4,2,1,1000)
        self.assertAlmostEqual(a,25)
        self.assertAlmostEqual(b,12.5)
        self.assertEqual(atr_position_size(10000,.01,2,2,1,10),10)
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
    def test_degradation_triggers_fallback_not_overfit_proof(self):
        ins=[.3]*200; oos=[.1]*100
        r=validate_expectancy(ins,oos,[[.1,.2],[.0,.1]],degradation_limit=.2,min_oos_trades=50)
        self.assertTrue(r.overfit_flag)
        self.assertEqual(r.decision,"REJECT_OR_FALLBACK")
    def test_nonpositive_insample_does_not_use_degradation_ratio(self):
        r=validate_expectancy([-.1,.1]*100,[.1,.2]*50,[[.1,.2],[.2,.3]],min_oos_trades=50)
        self.assertIsNone(r.degradation_pct)
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

if __name__=="__main__": unittest.main()
