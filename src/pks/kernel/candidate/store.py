from __future__ import annotations

from pathlib import Path

from pks.kernel.storage import read_yaml, write_yaml
from pks.models import Claim


class CandidateStore:
    def __init__(self, capsule_path: Path) -> None:
        self.capsule_path = capsule_path
        self.candidates_dir = capsule_path / "candidates"

    def save(self, claim: Claim) -> None:
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        write_yaml(
            self.candidate_path(claim.claim_id),
            claim.model_dump(mode="json", exclude_none=True),
        )

    def load(self, candidate_id: str) -> Claim:
        return Claim.model_validate(read_yaml(self.candidate_path(candidate_id)))

    def list(self) -> list[Claim]:
        if not self.candidates_dir.exists():
            return []
        return [
            Claim.model_validate(read_yaml(path))
            for path in sorted(self.candidates_dir.glob("*.yaml"))
        ]

    def delete(self, candidate_id: str) -> None:
        self.candidate_path(candidate_id).unlink(missing_ok=False)

    def candidate_path(self, candidate_id: str) -> Path:
        return self.candidates_dir / f"{candidate_id}.yaml"
