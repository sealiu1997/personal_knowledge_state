from __future__ import annotations

from pathlib import Path

from pks.kernel.storage import read_yaml, write_yaml
from pks.models import Claim


class ClaimStore:
    def __init__(self, capsule_path: Path) -> None:
        self.capsule_path = capsule_path
        self.claims_dir = capsule_path / "claims"

    def save(self, claim: Claim) -> None:
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        write_yaml(
            self.claim_path(claim.claim_id),
            claim.model_dump(mode="json", exclude_none=True),
        )

    def load(self, claim_id: str) -> Claim:
        return Claim.model_validate(read_yaml(self.claim_path(claim_id)))

    def list(self) -> list[Claim]:
        if not self.claims_dir.exists():
            return []
        return [
            Claim.model_validate(read_yaml(path))
            for path in sorted(self.claims_dir.glob("*.yaml"))
        ]

    def claim_path(self, claim_id: str) -> Path:
        return self.claims_dir / f"{claim_id}.yaml"
