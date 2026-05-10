from __future__ import annotations

from pathlib import Path

from pks.kernel.candidate.store import CandidateStore
from pks.models import Claim, ClaimStatus


class CandidateQueue:
    def __init__(self, capsule_path: Path, store: CandidateStore | None = None) -> None:
        self.capsule_path = capsule_path
        self.store = store or CandidateStore(capsule_path)

    def submit(self, claim: Claim) -> Claim:
        claim.status = ClaimStatus.CANDIDATE.value
        self.store.save(claim)
        return claim

    def list(self) -> list[Claim]:
        return self.store.list()

    def load(self, candidate_id: str) -> Claim:
        return self.store.load(candidate_id)

    def delete(self, candidate_id: str) -> None:
        self.store.delete(candidate_id)
