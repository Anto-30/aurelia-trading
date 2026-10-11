from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from research.labs.rth_orb_auction import Bar, opening_range, orb_close_candidate, approximate_profile, ContractSpec, Costs, contracts_for_risk
NY=ZoneInfo("America/New_York")
def b(ts,o,h,l,c,v=100,complete=True):
    return Bar(datetime.fromisoformat(ts).replace(tzinfo=NY),o,h,l,c,v,complete)
def test_opening_range_excludes_0945():
    bars=[b("2026-10-05T09:30:00",100,102,99,101),b("2026-10-05T09:35:00",101,103,100,102),b("2026-10-05T09:40:00",102,104,101,103),b("2026-10-05T09:45:00",103,110,103,109)]
    assert opening_range(bars,datetime(2026,10,5).date())==(104,99)
def test_no_entry_before_0945():
    bar=b("2026-10-05T09:40:00",100,103,99,102)
    dt=datetime.fromisoformat("2026-10-05T09:40:00").replace(tzinfo=NY)
    assert orb_close_candidate(bar,101,98,dt)["strategy"]=="NO_TRADE"
def test_future_bar_blocked():
    bar=b("2026-10-05T10:00:00",100,103,99,102)
    dt=datetime.fromisoformat("2026-10-05T09:55:00").replace(tzinfo=NY)
    assert orb_close_candidate(bar,101,98,dt)["reason"]=="future bar"
def test_profile_is_labeled_approximate():
    p=approximate_profile([b("2026-10-05T10:00:00",100,102,100,101,300)],1)
    assert "not true VAP" in p["method"] and p["total_volume"]==pytest.approx(300)
def test_zero_contracts_when_budget_insufficient():
    assert contracts_for_risk(100,20000,19990,ContractSpec("MNQ",.25,.5,2),Costs(2),.0025)==0
def test_incomplete_bar_rejected():
    with pytest.raises(ValueError): b("2026-10-05T10:00:00",100,101,99,100,complete=False).validate()
