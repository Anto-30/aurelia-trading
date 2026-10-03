from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeploymentAttestation:
    source_commit: str
    build_hash: str
    artifact_hash: str
    deployment_id: str
    runtime_hash: str
    config_hash: str
    runtime_matches_artifact: bool

    def valid(self) -> bool:
        return all([
            self.source_commit,
            self.build_hash,
            self.artifact_hash,
            self.deployment_id,
            self.runtime_hash,
            self.config_hash,
            self.runtime_matches_artifact,
        ])


def write_attestation(path: str | Path, attestation: DeploymentAttestation) -> None:
    if not attestation.valid():
        raise ValueError("INVALID_DEPLOYMENT_ATTESTATION")
    Path(path).write_text(
        "\n".join(f"{k}={v}" for k, v in attestation.__dict__.items()) + "\n",
        encoding="utf-8",
    )
