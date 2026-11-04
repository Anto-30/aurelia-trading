"""Fail-closed, research-only contract boundary for NVIDIA Auto Ontology.

This package does not connect to databases, execute SQL, call MCP, or authorize
capital movement. It validates evidence envelopes before a separately reviewed
read-only adapter may consume them.
"""

from .contract import (
    EvidenceEnvelope,
    EvidenceValidationError,
    QueryPolicy,
    validate_evidence,
)

__all__ = [
    "EvidenceEnvelope",
    "EvidenceValidationError",
    "QueryPolicy",
    "validate_evidence",
]
