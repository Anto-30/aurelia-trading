from assurance.release_evidence_gate import gate

def base_research():
    return {
        "qualification_status": "RESEARCH_QUALIFIED",
        "oos_observations": 100,
        "oos_mean_strategy_return": 0.001,
        "execution_economics": {"quoted_contract_economics": {"sample_count": 100, "mean_net_return_per_stake": 0.01}},
        "probability": {"calibration_status": "VALIDATED_RESEARCH", "drift_detected": False},
        "campaign_complete": True,
    }

def base_broker():
    return {
        "verification_scope": "REAL_DERIV_TRANSACTION_LIFECYCLE",
        "orders_submitted": 1,
        "capital_authority_granted": True,
        "observed": {"reconciliation_healthy": True},
    }

def base_deploy():
    return {"status": "DEPLOYED_AND_HEALTHCHECKED", "capital_protection": True}

def test_incomplete_broker_evidence_blocks():
    status, reasons = gate(base_research(), {"verification_scope": "REAL_DERIV_LIFECYCLE_VERIFY_ONLY", "orders_submitted": 0}, base_deploy())
    assert status == "NOT_READY"
    assert "REAL_TRANSACTION_LIFECYCLE_EVIDENCE_MISSING" in reasons

def test_complete_evidence_is_complete():
    status, reasons = gate(base_research(), base_broker(), base_deploy())
    assert status == "RELEASE_EVIDENCE_COMPLETE"
    assert reasons == []
