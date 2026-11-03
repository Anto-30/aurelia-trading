from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from runtime.core.models import BrokerOutcome


@dataclass(frozen=True)
class BrokerLifecycleRecord:
    intent_id: str
    proposal_id: str | None = None
    transaction_id: str | None = None
    contract_id: str | None = None
    outcome: BrokerOutcome = BrokerOutcome.UNKNOWN
    observed_at: datetime | None = None
    reconciled: bool = False

    def with_broker_acceptance(self, transaction_id: str | None, contract_id: str | None):
        return BrokerLifecycleRecord(
            intent_id=self.intent_id,
            proposal_id=self.proposal_id,
            transaction_id=transaction_id,
            contract_id=contract_id,
            outcome=BrokerOutcome.ACCEPTED,
            observed_at=datetime.now(timezone.utc),
            reconciled=False,
        )

    def settled(self):
        return BrokerLifecycleRecord(
            intent_id=self.intent_id,
            proposal_id=self.proposal_id,
            transaction_id=self.transaction_id,
            contract_id=self.contract_id,
            outcome=BrokerOutcome.SETTLED,
            observed_at=datetime.now(timezone.utc),
            reconciled=self.reconciled,
        )


async def monitor_contract(adapter, contract_id: str) -> AsyncIterator[dict[str, Any]]:
    '''Continuously query contract status until broker marks it closed.'''
    while True:
        status = await adapter.get_contract_status(contract_id)
        yield status
        is_sold = bool(status.get("is_sold"))
        status_value = str(status.get("status") or "").lower()
        if is_sold or status_value in {"sold", "closed", "won", "lost", "expired"}:
            return


# Assurance orchestration is integrated into this existing broker lifecycle module.
# It only accepts an already-created adapter and its already-connected transport.
# It does not construct sockets, authenticate, reconnect, or submit transactions.
from dataclasses import field
from typing import Mapping
from uuid import UUID


@dataclass
class AssuranceReport:
    aurelia_uuid: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "RUNNING"
    failure_reason: str | None = None
    identity_verified: bool = False
    evidence_acquired: bool = False
    lifecycle_assessment_completed: bool = False
    stake_reconciliation: dict[str, Any] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    transport_reused: bool = True
    new_connections_created: int = 0


class AURELIABrokerLifecycleAssurance:
    """Run assurance phases over an adapter and transport owned by AURELIA.

    The verifier, evidence acquirer, lifecycle assessor, and policy registry are
    injected from their owning modules. This orchestrator deliberately has no
    WebSocket factory, token, OTP, connect, reconnect, or order-submission path.

    A connected authenticated account adapter is only eligible where the
    provider and account permission are independently established as read-only.
    This class does not override the account-plane gate.
    """

    REQUIRED_EVIDENCE_KEYS = frozenset({
        "identity",
        "balance",
        "account_status",
        "portfolio",
        "statement",
        "timestamps",
        "provenance",
        "hashes",
    })
    FORBIDDEN_PII_KEYS = frozenset({
        "email",
        "email_address",
        "email_hash",
        "first_name",
        "last_name",
        "full_name",
        "phone",
        "phone_number",
        "access_token",
        "refresh_token",
        "auth_token",
        "otp",
        "password",
        "authorization",
        "cookie",
    })

    def __init__(
        self,
        *,
        existing_adapter: Any,
        aurelia_uuid: str,
        identity_verifier: Any,
        evidence_acquirer: Any,
        lifecycle_assessor: Any,
        stake_policy_registry: Any,
    ) -> None:
        if existing_adapter is None:
            raise ValueError("EXISTING_AURELIA_ADAPTER_REQUIRED")
        canonical_transport = getattr(existing_adapter, "transport", None)
        if canonical_transport is None:
            raise ValueError("CANONICAL_AURELIA_TRANSPORT_REQUIRED")
        try:
            UUID(aurelia_uuid)
        except (TypeError, ValueError, AttributeError):
            raise ValueError("AURELIA_UUID_INVALID") from None

        for label, component in (
            ("IDENTITY_VERIFIER", identity_verifier),
            ("EVIDENCE_ACQUIRER", evidence_acquirer),
        ):
            component_transport = getattr(component, "transport", canonical_transport)
            if component_transport is not canonical_transport:
                raise ValueError(f"{label}_MUST_USE_CANONICAL_TRANSPORT")

        if not callable(getattr(identity_verifier, "verify_complete_identity", None)):
            raise TypeError("IDENTITY_VERIFIER_INTERFACE_INVALID")
        if not callable(getattr(evidence_acquirer, "acquire_extended_evidence", None)):
            raise TypeError("EVIDENCE_ACQUIRER_INTERFACE_INVALID")
        if not callable(getattr(lifecycle_assessor, "execute_lifecycle_tests", None)):
            raise TypeError("LIFECYCLE_ASSESSOR_INTERFACE_INVALID")
        if not callable(getattr(stake_policy_registry, "export_reconciliation_report", None)):
            raise TypeError("STAKE_POLICY_REGISTRY_INTERFACE_INVALID")

        self.adapter = existing_adapter
        self.transport = canonical_transport
        self.aurelia_uuid = aurelia_uuid
        self.identity_verifier = identity_verifier
        self.evidence_acquirer = evidence_acquirer
        self.lifecycle_assessor = lifecycle_assessor
        self.stake_policy_registry = stake_policy_registry

    def _assert_canonical_transport_unchanged(self) -> None:
        if getattr(self.adapter, "transport", None) is not self.transport:
            raise RuntimeError("CANONICAL_TRANSPORT_REPLACED_DURING_ASSURANCE")

    @classmethod
    def _validate_evidence_shape(cls, evidence: Any) -> dict[str, Any]:
        if not isinstance(evidence, Mapping):
            raise ValueError("ASSURANCE_EVIDENCE_NOT_A_MAPPING")
        missing = cls.REQUIRED_EVIDENCE_KEYS.difference(evidence.keys())
        if missing:
            raise ValueError("ASSURANCE_EVIDENCE_FIELDS_MISSING:" + ",".join(sorted(missing)))

        def scan(value: Any) -> None:
            if isinstance(value, Mapping):
                for key, child in value.items():
                    if str(key).strip().lower() in cls.FORBIDDEN_PII_KEYS:
                        raise ValueError("ASSURANCE_EVIDENCE_CONTAINS_FORBIDDEN_PII")
                    scan(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    scan(child)

        scan(evidence)
        return dict(evidence)

    async def execute_complete_assurance(self) -> AssuranceReport:
        report = AssuranceReport(
            aurelia_uuid=self.aurelia_uuid,
            started_at=datetime.now(timezone.utc),
        )
        try:
            self._assert_canonical_transport_unchanged()
            identity = await self.identity_verifier.verify_complete_identity()
            if not callable(getattr(identity, "validate_integrity", None)):
                raise ValueError("COMPOSITE_IDENTITY_INTERFACE_INVALID")
            if identity.validate_integrity() is not True:
                raise ValueError("COMPOSITE_IDENTITY_INTEGRITY_FAILED")
            report.identity_verified = True
            self._assert_canonical_transport_unchanged()

            evidence = await self.evidence_acquirer.acquire_extended_evidence(identity)
            report.evidence = self._validate_evidence_shape(evidence)
            report.evidence_acquired = True
            self._assert_canonical_transport_unchanged()

            lifecycle = await self.lifecycle_assessor.execute_lifecycle_tests(
                adapter=self.adapter,
                identity=identity,
                evidence=report.evidence,
            )
            if not isinstance(lifecycle, Mapping):
                raise ValueError("LIFECYCLE_ASSESSMENT_INVALID")
            report.evidence["lifecycle"] = dict(lifecycle)
            report.lifecycle_assessment_completed = True
            self._assert_canonical_transport_unchanged()

            policy_report = self.stake_policy_registry.export_reconciliation_report()
            if not isinstance(policy_report, dict):
                raise ValueError("STAKE_POLICY_RECONCILIATION_INVALID")
            report.stake_reconciliation = policy_report
            report.status = "COMPLETED"
        except Exception as exc:
            report.status = "FAILED"
            # Exception messages may contain URLs, tokens, or account data.
            report.failure_reason = type(exc).__name__
        finally:
            report.completed_at = datetime.now(timezone.utc)
            report.transport_reused = getattr(self.adapter, "transport", None) is self.transport
            report.new_connections_created = 0
        return report
