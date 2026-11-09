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
