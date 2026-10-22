import importlib.util,json
from pathlib import Path
import pandas as pd
import pytest
P=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("sim",P/"scripts/run_msnr_simulator.py"); sim=importlib.util.module_from_spec(sp); sp.loader.exec_module(sim)
def test_missing_economics_rejected(tmp_path):
 p=tmp_path/"spec.json"; p.write_text(json.dumps({"pip_size":None,"multiplier":None,"spread_pips":2,"slippage_bps":5,"account_risk_pct":.01,"initial_equity":None,"independently_verified":False,"contract_type":"linear_cfd"}))
 with pytest.raises(ValueError,match="UNVERIFIED"): sim.load_specs(p)
def test_binary_rejected(tmp_path):
 p=tmp_path/"spec.json"; p.write_text(json.dumps({"pip_size":1,"multiplier":1,"spread_pips":2,"slippage_bps":5,"account_risk_pct":.01,"initial_equity":100,"independently_verified":True,"contract_type":"binary"}))
 with pytest.raises(ValueError,match="Only linear"): sim.load_specs(p)
def test_features_warmup_not_filled():
 d=pd.DataFrame({"epoch":range(250),"open":[100+i*.1 for i in range(250)],"high":[101+i*.1 for i in range(250)],"low":[99+i*.1 for i in range(250)],"close":[100+i*.1 for i in range(250)]})
 x=sim.features(d); assert pd.isna(x.ma200.iloc[198]); assert pd.isna(x.prior_low.iloc[0]); assert "long_signal" in x
def test_explicit_seed(): assert sim.SEED==42


def test_simulator_fails_closed_before_data_access(tmp_path):
    specs=tmp_path/"spec.json"
    specs.write_text(json.dumps({"pip_size":None,"multiplier":None,"spread_pips":2,"slippage_bps":5,"account_risk_pct":0.01,"initial_equity":None,"independently_verified":False,"contract_type":"linear_cfd"}))
    args=type("Args",(),{"data":str(tmp_path/"does-not-exist.csv"),"specs":str(specs),"ledger":str(tmp_path/"ledger.jsonl"),"start":"2022-10-21","end":"2024-10-21","commit_sha":"test"})()
    with pytest.raises(ValueError,match="UNVERIFIED"):
        sim.run(args)
