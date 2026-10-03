from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseLineage:
    current_source_commit: str
    current_artifact_hash: str
    previous_source_commit: str
    previous_artifact_hash: str

    def rollback_target_valid(self) -> bool:
        return bool(
            self.previous_source_commit
            and self.previous_artifact_hash
            and self.previous_source_commit != self.current_source_commit
        )


def can_rollback_with_new_exposure_blocked(lineage: ReleaseLineage, exposure_open: bool) -> bool:
    return lineage.rollback_target_valid() and not exposure_open
