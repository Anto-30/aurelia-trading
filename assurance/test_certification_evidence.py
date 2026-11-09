from assurance.certification_evidence import _domain_valid, _provenance_valid


def verify_only_record():
    return {
        "verification_scope": "REAL_DERIV_LIFECYCLE_VERIFY_ONLY",
        "orders_submitted": 0,
        "capital_authority_granted": False,
        "order_submission_permitted": False,
        "observed": {
            "mode": "VERIFY_ONLY",
            "account_loginid": "CRTEST",
            "proposal_id": "proposal-test",
            "intent_id": "intent-test",
            "risk_approved": True,
            "firewall_approved": True,
            "reconciliation_healthy": True,
            "fence_valid": True,
            "broker_submission_performed": False,
            "capital_movement": False,
        },
    }


def test_verify_only_lifecycle_is_accepted_without_order_or_capital_movement():
    ok, detail = _domain_valid("broker_lifecycle.json", verify_only_record())
    assert ok, detail


def test_live_order_or_capital_authority_is_rejected_as_verify_only_evidence():
    record = verify_only_record()
    record["orders_submitted"] = 1
    ok, _ = _domain_valid("broker_lifecycle.json", record)
    assert not ok

    record = verify_only_record()
    record["capital_authority_granted"] = True
    ok, _ = _domain_valid("broker_lifecycle.json", record)
    assert not ok


def test_order_count_must_be_integer_zero_not_boolean_or_float():
    for invalid_count in (False, 0.0, "0", None, 1):
        record = verify_only_record()
        record["orders_submitted"] = invalid_count
        ok, _ = _domain_valid("broker_lifecycle.json", record)
        assert not ok


def test_real_deriv_environment_is_valid_runtime_provenance():
    record = {
        "environment": "real",
        "provenance": {
            "origin": "runtime",
            "issuer": "aurelia-deriv-lifecycle-verifier",
            "source_commit": "a" * 40,
            "generated_at_utc": "2026-11-09T10:00:00+00:00",
            "deployment_id": "DERIV-VERIFY-ONLY",
        },
    }
    ok, detail = _provenance_valid(record)
    assert ok, detail

def test_execution_economics_sample_count_must_be_exact_integer():
    valid = {
        "net_expectancy_status": "KNOWN",
        "stress_passed": True,
        "sample_count": 1,
        "cost_components": {"spread": 0.01},
        "execution_model": "conservative",
    }
    ok, detail = _domain_valid("execution_economics.json", valid)
    assert ok, detail

    for invalid_count in (True, 1.0, "1", None, 0):
        record = dict(valid)
        record["sample_count"] = invalid_count
        ok, _ = _domain_valid("execution_economics.json", record)
        assert not ok


def test_recovery_counters_must_be_exact_integer_zero():
    record = {
        "critical_scenarios_passed": True,
        "scenario_results": [{"passed": True}, {"passed": True}, {"passed": True}],
        "blind_resubmissions": 0,
        "duplicate_economic_effects": 0,
    }
    ok, detail = _domain_valid("recovery_matrix.json", record)
    assert ok, detail
    record["blind_resubmissions"] = False
    ok, _ = _domain_valid("recovery_matrix.json", record)
    assert not ok


def test_soak_counters_must_be_exact_integer_zero():
    record = {
        "duration_seconds": 3600,
        "actual_elapsed_seconds": 3600.0,
        "continuous": True,
        "execution_mode": "VERIFY_ONLY",
        "deployment_id": "deployment-test",
        "runtime_instance_id": "runtime-test",
        "invariant_violations": 0,
        "silent_degradations": 0,
        "capital_authority_escapes": 0,
        "unresolved_unknown_states": 0,
    }
    ok, detail = _domain_valid("soak_3600s.json", record)
    assert ok, detail
    record["invariant_violations"] = False
    ok, _ = _domain_valid("soak_3600s.json", record)
    assert not ok


def test_security_audit_critical_findings_must_be_exact_integer_zero():
    record = {
        "credential_isolation_passed": True,
        "capital_bypass_audit_passed": True,
        "audit_id": "audit-test",
        "auditor": "independent-reviewer",
        "scope": "credential and capital authority",
        "findings": [{"severity": "INFO"}],
        "critical_findings": 0,
    }
    ok, detail = _domain_valid("security_audit.json", record)
    assert ok, detail
    record["critical_findings"] = False
    ok, _ = _domain_valid("security_audit.json", record)
    assert not ok
