from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "deriv-payment-agent.openapi.yaml"


def _section(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at + len(start))
    return source[start_at:end_at]


def test_upstream_snapshot_is_pinned_without_claiming_live_identity() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    pin = _section(contract, "x-aurelia-upstream-source:", "\ntags:")

    assert "release_tag: production_v20260901_0" in pin
    assert "git_commit: 54e353807146d31f58291693243cbbf671de7bce" in pin
    assert "source_blob_sha: b785658de90b1c8010629f90b81c9441fa119f74" in pin
    assert (
        "sha256: 8a2655d9b9713f65296035ba02f8cf6f281ab95fcf454dd996b763a53506682f"
        in pin
    )
    assert "content_bytes: 241091" in pin
    assert "direct_live_endpoint_identity_verified: false" in pin


def test_directory_list_matches_the_pinned_official_array_contract() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    list_route = _section(
        contract, "  /payment-agents/v1/agents:\n", "  /payment-agents/v1/agents/{id}:"
    )
    # Actual schema order is allowed to move: validate the list item definition separately.
    list_item = _section(contract, "    PaymentAgentListItem:", "    DirectoryEnvelope:")
    directory = contract[contract.index("    DirectoryEnvelope:") :]

    assert "required: true" in list_route
    assert "pattern: '^[A-Z_]{1,18}$'" in _section(
        contract, "    Currency:", "    Amount:"
    )
    assert "default: 1" in list_route
    assert "default: 25" in list_route
    assert "'400': { $ref: '#/components/responses/BadRequest' }" in list_route
    assert "schema: { $ref: '#/components/schemas/DirectoryEnvelope' }" in list_route
    assert "required: [data, errors, metadata]" in directory
    assert "data:" in directory
    assert "type: array" in directory
    assert "items: { $ref: '#/components/schemas/PaymentAgentListItem' }" in directory
    assert "oneOf:" not in directory
    assert "required: [id]" in list_item
    assert "deposit_commission: { type: [number, 'null'] }" in list_item
    assert "withdrawal_minimum: { type: [string, 'null'] }" in list_item


def test_agent_id_and_standard_error_envelope_match_official_shape() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    agent_route = _section(
        contract, "  /payment-agents/v1/agents/{id}:",
        "  /payment-agents/v1/clients/me:"
    )
    error = _section(contract, "    ApiError:", "    ErrorEnvelope:")
    envelope = _section(contract, "    ErrorEnvelope:", "    StatisticsEnvelope:")

    assert "pattern: '^(?:[1-9]\\d*|me)$'" in agent_route
    assert "required: [status, code]" in error
    assert "message: { type: string }" not in error
    assert "detail:" in error
    assert "required: [data, errors, metadata]" in envelope


def test_contract_keeps_all_external_side_effects_deny_by_default() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")
    for expected in (
        "defaultMode: TEST_ONLY",
        "liveMoneyWritesPermitted: false",
        "fakeTransportRequiredForTests: true",
        "verificationCodeDispatchPermitted: false",
        "clientPrivacyMutationsPermitted: false",
        "neverBlindlyResubmitAmbiguousWrite: true",
    ):
        assert expected in contract
