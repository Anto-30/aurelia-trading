"""Execution-neutral hardening predicates for AURELIA.

These controls are assurance contracts. They never submit orders, create broker
sessions, or grant capital authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Iterable, Mapping, Optional


EVIDENCE_CURRENT_STATES = {"CURRENT", "EXPIRING"}

@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_hash: str
    artifact_hash: str
    config_hash: str
    data_hash: str
    environment: str
    started_at_utc: str
    ended_at_utc: str
    status: str
    valid_until_utc: Optional[str] = None

@dataclass(frozen=True)
class MarketDataIntegrity:
    stale: bool
    duplicate: bool
    out_of_order: bool
    malformed: bool
    symbol_matched: bool
    timestamp_valid: bool

@dataclass(frozen=True)
class ExposureSnapshot:
    existing: float
    pending: float
    concurrent_intents: float
    correlated: float
    new_order: float
    hard_limit: float

def _parse_utc(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)

def evidence_is_current(record: EvidenceRecord, now_utc: str) -> bool:
    if record.status not in EVIDENCE_CURRENT_STATES:
        return False
    try:
        ended = _parse_utc(record.ended_at_utc)
        now = _parse_utc(now_utc)
        if record.valid_until_utc and now >= _parse_utc(record.valid_until_utc):
            return False
        return ended <= now
    except (TypeError, ValueError):
        return False

def evidence_chain_complete(record: EvidenceRecord) -> bool:
    required = (
        record.evidence_id, record.source_hash, record.artifact_hash,
        record.config_hash, record.data_hash, record.environment,
        record.started_at_utc, record.ended_at_utc,
    )
    return all(isinstance(v, str) and v.strip() for v in required)

def market_data_safe(x: MarketDataIntegrity) -> bool:
    return not any((x.stale, x.duplicate, x.out_of_order, x.malformed)) and all(
        (x.symbol_matched, x.timestamp_valid)
    )

def mtf_snapshot_is_decision_time_safe(snapshot_times: Iterable[str], decision_time_utc: str) -> bool:
    try:
        decision = _parse_utc(decision_time_utc)
        return all(_parse_utc(ts) <= decision for ts in snapshot_times)
    except (TypeError, ValueError):
        return False

def stake_ceiling_from_verified_balance(balance: Optional[float]) -> Optional[float]:
    """Verified available balance is the maximum capital the order layer may
    request. Deterministic risk may impose a lower ceiling."""
    if balance is None or not isfinite(balance) or balance < 0:
        return None
    return balance

def requested_stake_is_balance_permitted(
    balance: Optional[float],
    requested_stake: Optional[float],
    minimum_stake: float = 1.00,
) -> bool:
    """Affordability permits a request up to 100% of verified available balance.
    
    For low balances (< 2.0), stake must be strictly less than balance.
    For normal balances (>= 2.0), stake can equal balance.
    
    Args:
        balance: Verified available balance
        requested_stake: Proposed stake amount
        minimum_stake: Minimum stake threshold (default 1.00)
    
    Returns:
        True if stake is permitted given balance constraints
    """
    if balance is None or requested_stake is None:
        return False
    if not all(isfinite(v) for v in (balance, requested_stake, minimum_stake)):
        return False
    if requested_stake < minimum_stake or requested_stake <= 0:
        return False
    
    # For low balances, enforce strict inequality: stake < balance
    if balance < 2.0:
        return requested_stake < balance
    
    # For normal balances, allow stake <= balance
    return requested_stake <= balance

def full_balance_stake_is_affordable(
    balance: Optional[float],
    minimum_stake: float = 1.00,
) -> bool:
    ceiling = stake_ceiling_from_verified_balance(balance)
    return ceiling is not None and requested_stake_is_balance_permitted(
        ceiling, ceiling, minimum_stake
    )

def exposure_within_limit(x: ExposureSnapshot) -> bool:
    values = (x.existing, x.pending, x.concurrent_intents, x.correlated, x.new_order, x.hard_limit)
    if not all(isfinite(v) for v in values):
        return False
    if min(values) < 0:
        return False
    return (
        x.existing + x.pending + x.concurrent_intents + x.correlated + x.new_order
        <= x.hard_limit
    )

def exactly_once_economic_effect(intent_count: int, economic_effect_count: int) -> bool:
    return intent_count >= 0 and economic_effect_count in (0, 1) and economic_effect_count <= intent_count

def unknown_broker_state_is_actionable(unknown: bool) -> bool:
    return not unknown

def kill_switch_resume_requires_new_authorization(
    kill_switch_on: bool,
    prior_authorization_valid: bool,
    new_authorization_present: bool,
) -> bool:
    if kill_switch_on:
        return False
    if not prior_authorization_valid:
        return True
    return new_authorization_present

def configuration_hash_matches(approved_hash: str, runtime_hash: str) -> bool:
    return bool(approved_hash and runtime_hash and approved_hash == runtime_hash)

def shadow_decision_equivalent(
    expected_action: str,
    shadow_action: str,
    expected_authorization: str,
    shadow_authorization: str,
) -> bool:
    return expected_action == shadow_action and expected_authorization == shadow_authorization

def privilege_allows(action: str, *, actor: str, capital_authority: Mapping[str, bool]) -> bool:
    if action in {"SUBMIT_ORDER", "CANCEL_ORDER", "MODIFY_ORDER"}:
        return bool(capital_authority.get(actor, False))
    return True
