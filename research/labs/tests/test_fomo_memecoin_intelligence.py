from __future__ import annotations

from dataclasses import replace

import pytest

from research.fomo_memecoin_intelligence import (
    EvidenceRef,
    HolderMetrics,
    MarketMetrics,
    MemecoinResearchCandidate,
    ResearchStatus,
    SocialMetrics,
    TokenSafety,
    TraderMetrics,
    research_candidate,
    research_decision_cannot_authorize_execution,
    validate_calibrated_probability,
)


def evidence() -> tuple[EvidenceRef, ...]:
    return (
        EvidenceRef(
            source="https://example.invalid/token",
            source_timestamp_utc="2026-10-05T12:00:00Z",
            collected_timestamp_utc="2026-10-05T12:01:00Z",
            verified=True,
        ),
    )


def candidate() -> MemecoinResearchCandidate:
    return MemecoinResearchCandidate(
        candidate_id="solana-demo-001",
        token_mint="DemoMint111111111111111111111111111111111111",
        chain="solana",
        narrative="Verified narrative",
        catalyst="Verified catalyst",
        thesis="Continuation requires sustained demand after the catalyst.",
        invalidation="Liquidity collapse or catalyst failure invalidates the thesis.",
        gross_expected_return=0.30,
        fees=0.01,
        slippage_cost=0.02,
        market_impact_cost=0.03,
        execution_degradation_cost=0.01,
        market=MarketMetrics(
            market_cap_usd=2_000_000,
            liquidity_usd=250_000,
            volume_24h_usd=1_000_000,
            spread_bps=20,
            slippage_bps=40,
            price_impact_bps=30,
            execution_degradation_bps=20,
            exitability_score=0.85,
        ),
        holders=HolderMetrics(
            holder_count=2_000,
            top10_concentration=0.25,
            wallet_concentration=0.45,
        ),
        safety=TokenSafety(
            identity_verified=True,
            mint_authority_revoked=True,
            freeze_authority_revoked=True,
            upgradeability_known=True,
            liquidity_control_known=True,
        ),
        evidence=evidence(),
        probability=0.65,
        probability_is_calibrated=True,
        trader=TraderMetrics(
            completed_trades=120,
            realized_return=1.20,
            max_drawdown=0.20,
            win_rate=0.60,
            profit_factor=2.0,
            expectancy=0.02,
            median_hold_seconds=8_640,
        ),
        social=SocialMetrics(
            independently_verified_sources=3,
            source_credibility=0.80,
            novelty=0.70,
            engagement_quality=0.75,
            contradiction_rate=0.10,
        ),
    )


def test_strong_candidate_can_qualify_but_never_authorizes_execution() -> None:
    decision = research_candidate(candidate())
    assert decision.status is ResearchStatus.RESEARCH_QUALIFIED
    assert decision.net_expected_edge == pytest.approx(0.23)
    assert decision.trade_probability_valid is True
    assert decision.calibrated_probability == pytest.approx(0.65)
    assert decision.execution_authorized is False
    assert decision.authorization_scope == "RESEARCH_ONLY"
    research_decision_cannot_authorize_execution(decision)


@pytest.mark.parametrize("probability", [0.54, 0.76, 0.82, None])
def test_probability_policy_is_strict_and_non_clipping(probability: float | None) -> None:
    assert validate_calibrated_probability(probability, calibrated=True) is (
        probability is not None and 0.55 <= probability <= 0.75
    )


def test_invalid_probability_blocks_research_qualification() -> None:
    decision = research_candidate(replace(candidate(), probability=0.82))
    assert decision.status is ResearchStatus.UNKNOWN
    assert decision.trade_probability_valid is False
    assert "TRADE_PROBABILITY_INVALID_OR_UNCALIBRATED" in decision.reasons
    assert decision.execution_authorized is False


def test_costs_can_erase_gross_edge() -> None:
    decision = research_candidate(
        replace(
            candidate(),
            gross_expected_return=0.04,
            fees=0.01,
            slippage_cost=0.015,
            market_impact_cost=0.01,
            execution_degradation_cost=0.01,
        )
    )
    assert decision.status is ResearchStatus.RESEARCH_REJECTED
    assert decision.net_expected_edge == pytest.approx(-0.005)
    assert "NET_EXPECTED_EDGE_NON_POSITIVE" in decision.reasons


def test_unknown_safety_never_becomes_safe() -> None:
    decision = research_candidate(
        replace(candidate(), safety=replace(candidate().safety, mint_authority_revoked=None))
    )
    assert decision.status is ResearchStatus.UNKNOWN
    assert "MINT_AUTHORITY_UNKNOWN" in decision.reasons
    assert decision.execution_authorized is False


def test_active_mint_authority_is_rejected() -> None:
    decision = research_candidate(
        replace(candidate(), safety=replace(candidate().safety, mint_authority_revoked=False))
    )
    assert decision.status is ResearchStatus.RESEARCH_REJECTED
    assert "MINT_AUTHORITY_ACTIVE" in decision.reasons


def test_trend_only_is_not_a_thesis() -> None:
    decision = research_candidate(replace(candidate(), trend_only=True))
    assert decision.status is ResearchStatus.RESEARCH_REJECTED
    assert "TREND_ONLY_NO_THESIS" in decision.reasons


def test_holder_concentration_is_a_first_class_risk() -> None:
    decision = research_candidate(
        replace(candidate(), holders=replace(candidate().holders, top10_concentration=0.60))
    )
    assert decision.status is ResearchStatus.RESEARCH_REJECTED
    assert "TOP10_CONCENTRATION_TOO_HIGH" in decision.reasons


def test_low_exitability_is_rejected() -> None:
    decision = research_candidate(
        replace(candidate(), market=replace(candidate().market, exitability_score=0.40))
    )
    assert decision.status is ResearchStatus.RESEARCH_REJECTED
    assert "EXITABILITY_TOO_LOW" in decision.reasons


def test_unverified_social_or_source_evidence_is_not_authoritative() -> None:
    unverified = EvidenceRef(
        source="https://example.invalid/social",
        source_timestamp_utc="2026-10-05T12:00:00Z",
        collected_timestamp_utc="2026-10-05T12:01:00Z",
        verified=False,
    )
    decision = research_candidate(replace(candidate(), evidence=(unverified,)))
    assert decision.status is ResearchStatus.UNKNOWN
    assert "UNVERIFIED_EVIDENCE" in decision.reasons
    assert decision.execution_authorized is False


def test_stale_or_reversed_evidence_timestamps_fail_closed() -> None:
    invalid = EvidenceRef(
        source="https://example.invalid/social",
        source_timestamp_utc="2026-10-05T12:01:00Z",
        collected_timestamp_utc="2026-10-05T12:00:00Z",
        verified=True,
    )
    with pytest.raises(ValueError, match="collected timestamp"):
        research_candidate(replace(candidate(), evidence=(invalid,)))


def test_provenance_hash_is_stable_for_identical_inputs() -> None:
    first = research_candidate(candidate())
    second = research_candidate(candidate())
    assert first.provenance_hash == second.provenance_hash
