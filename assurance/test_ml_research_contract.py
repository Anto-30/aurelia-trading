import unittest
from research.ml.resnls import ResNLSConfig
from research.ml.schema import MLEvidence,reject_future_features,validate_feature_vector
from research.ml.timing import BarTiming,timing_features
from research.ml.promotion import PromotionEvidence,promotion_decision
class MLResearchContractTests(unittest.TestCase):
    def test_timing(self):
        x=timing_features(BarTiming(0,2,5,10)); self.assertAlmostEqual(x["high_time_position"],.2)
    def test_unfinished_extreme_rejected(self):
        with self.assertRaises(ValueError): timing_features(BarTiming(0,11,5,10))
    def test_future_feature_rejected(self):
        with self.assertRaises(ValueError): reject_future_features({"future":101},100)
    def test_feature_schema(self):
        validate_feature_vector(["a","b"],[1,2])
        with self.assertRaises(ValueError): validate_feature_vector(["a"],[1,2])
    def test_evidence(self):
        MLEvidence("RLSTM-IBTI-v0.1","LONG",.65,.01,-.005,.02,"TREND","PASS","PASS","FRESH").validate()
    def test_promotion(self):
        self.assertEqual(promotion_decision(PromotionEvidence(True,True,True,True,True,True)),"PROMOTION_CANDIDATE")
        self.assertEqual(promotion_decision(PromotionEvidence(True,True,False,True,True,True)),"RESEARCH")
    def test_config(self): ResNLSConfig(input_features=12).validate()
if __name__=="__main__": unittest.main()
