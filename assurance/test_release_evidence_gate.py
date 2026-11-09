from assurance.release_evidence_gate import gate


def base_research():
    return {
        "qualification_status": "RESEARCH_QUALIFIED",
        "oos_observations": 100,
        "oos_mean_strategy_return": 0.001,
        "execution_economics": {
            "quoted_contract_economics": {
                "sample_count": 100,
                "mean_net_return_per_stake": 0.01,
            }
        },
        "probability": {
            "calibration_status": "VALIDATED_RESEARCH",
            "drift_detected": False,
        },
        "campaign_complete": True,
    }


def base_lifecycle():
    return {
        "verification_scope": "REAL_DERIV_LIFECYCLE_VERIFY_ONLY",
        "orders_submitted": 0,
        "capital_authority_granted": False,
        "observed": {
            "reconciliation_healthy": True,
            "broker_submission_performed": False,
            "capital_movement": False,
        },
    }


def base_deploy():
    return {
        "status": "DEPLOYED_AND_HEALTHCHECKED",
        "capital_protection": True,
    }


def test_incomplete_broker_evidence_blocks():
    lifecycle = base_lifecycle()
    lifecycle["verification_scope"] = "UNVERIFIED"
    status, reasons = gate(base_research(), lifecycle, base_deploy())
    assert status == "NOT_READY"
    assert "VERIFY_ONLY_LIFECYCLE_EVIDENCE_MISSING" in reasons


def test_verify_only_evidence_can_be_complete_without_capital_movement():
    status, reasons = gate(base_research(), base_lifecycle(), base_deploy())
    assert status == "EVIDENCE_COMPLETE_VERIFY_ONLY"
    assert reasons == []


def test_any_order_submission_blocks_verify_only_evidence():
    lifecycle = base_lifecycle()
    lifecycle["orders_submitted"] = 1
    status, reasons = gate(base_research(), lifecycle, base_deploy())
    assert status == "NOT_READY"
    assert "VERIFY_ONLY_LIFECYCLE_SUBMITTED_ORDERS" in reasons


def test_capital_authority_must_remain_false():
    lifecycle = base_lifecycle()
    lifecycle["capital_authority_granted"] = True
    status, reasons = gate(base_research(), lifecycle, base_deploy())
    assert status == "NOT_READY"
    assert "VERIFY_ONLY_LIFECYCLE_GRANTED_CAPITAL_AUTHORITY" in reasons


def test_missing_reconciliation_and_capital_protection_block():
    lifecycle = base_lifecycle()
    lifecycle["observed"]["reconciliation_healthy"] = False
    deployment = base_deploy()
    deployment["capital_protection"] = False
    status, reasons = gate(base_research(), lifecycle, deployment)
    assert status == "NOT_READY"
    assert "VERIFY_ONLY_RECONCILIATION_NOT_PROVEN" in reasons
    assert "DEPLOYMENT_CAPITAL_PROTECTION_NOT_PROVEN" in reasons
