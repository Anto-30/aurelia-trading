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


def test_order_count_must_be_integer_zero_not_boolean_or_float():
    for invalid_count in (False, 0.0, "0", None, 1):
        lifecycle = base_lifecycle()
        lifecycle["orders_submitted"] = invalid_count
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

def test_research_counts_flags_and_returns_are_strict_and_finite():
    invalid_cases = (
        ("oos_observations", False, "OOS_SAMPLE_LT_100"),
        ("oos_observations", "100", "OOS_SAMPLE_LT_100"),
        ("oos_observations", 100.0, "OOS_SAMPLE_LT_100"),
        ("oos_mean_strategy_return", float("nan"), "OOS_EXPECTANCY_NOT_POSITIVE"),
        ("oos_mean_strategy_return", float("inf"), "OOS_EXPECTANCY_NOT_POSITIVE"),
        ("oos_mean_strategy_return", 10 ** 10000, "OOS_EXPECTANCY_NOT_POSITIVE"),
        ("campaign_complete", "false", "RESEARCH_CAMPAIGN_NOT_COMPLETE"),
    )
    for key, value, expected_reason in invalid_cases:
        research = base_research()
        research[key] = value
        status, reasons = gate(research, base_lifecycle(), base_deploy())
        assert status == "NOT_READY"
        assert expected_reason in reasons

    for key, value in (
        ("sample_count", False),
        ("sample_count", "100"),
        ("sample_count", 100.0),
    ):
        research = base_research()
        research["execution_economics"]["quoted_contract_economics"][key] = value
        status, reasons = gate(research, base_lifecycle(), base_deploy())
        assert status == "NOT_READY"
        assert "QUOTED_ECONOMICS_SAMPLE_LT_100" in reasons

    research = base_research()
    research["execution_economics"]["quoted_contract_economics"][
        "mean_net_return_per_stake"
    ] = float("nan")
    status, reasons = gate(research, base_lifecycle(), base_deploy())
    assert status == "NOT_READY"
    assert "QUOTED_ECONOMICS_NOT_POSITIVE" in reasons
