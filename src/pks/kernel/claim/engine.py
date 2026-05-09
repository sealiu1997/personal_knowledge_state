from __future__ import annotations

from datetime import date
from pathlib import Path

from pks.kernel.audit import AuditLog
from pks.kernel.claim.store import ClaimStore
from pks.models import Claim, ClaimStatus


class ClaimEngine:
    def __init__(
        self,
        capsule_path: Path,
        audit_log: AuditLog | None = None,
        store: ClaimStore | None = None,
    ) -> None:
        self.capsule_path = capsule_path
        self.audit_log = audit_log
        self.store = store or ClaimStore(capsule_path)

    def submit_claim(self, claim: Claim) -> Claim:
        claim.status = ClaimStatus.CANDIDATE.value
        self.save_claim(claim)
        self._audit("claim.submitted", {"claim_id": claim.claim_id})
        return claim

    def accept_claim(self, claim_id: str, today: date | None = None) -> Claim:
        claim = self.load_claim(claim_id)
        conflicts = self.detect_conflicts(claim)
        if conflicts:
            claim.status = ClaimStatus.DISPUTED.value
            self.save_claim(claim)
            for conflict in conflicts:
                conflict.status = ClaimStatus.DISPUTED.value
                self.save_claim(conflict)
            self._audit(
                "claim.disputed",
                {"claim_id": claim.claim_id, "conflicts": [item.claim_id for item in conflicts]},
            )
            return claim

        claim.status = ClaimStatus.ACCEPTED.value
        if claim.last_verified is None:
            claim.last_verified = today or date.today()
        self.save_claim(claim)
        self._audit("claim.accepted", {"claim_id": claim.claim_id})
        return claim

    def expire_claim(self, claim_id: str) -> Claim:
        claim = self.load_claim(claim_id)
        claim.status = ClaimStatus.EXPIRED.value
        self.save_claim(claim)
        self._audit("claim.expired", {"claim_id": claim.claim_id})
        return claim

    def mark_claim_disputed(self, claim_id: str) -> Claim:
        claim = self.load_claim(claim_id)
        claim.status = ClaimStatus.DISPUTED.value
        self.save_claim(claim)
        self._audit("claim.disputed", {"claim_id": claim.claim_id})
        return claim

    def supersede_claim(self, old_claim_id: str, new_claim: Claim) -> Claim:
        old_claim = self.load_claim(old_claim_id)
        if old_claim.conflict_key != new_claim.conflict_key:
            raise ValueError("superseding claims must share the same subject and predicate")

        new_claim.supersedes = old_claim.claim_id
        new_claim.status = ClaimStatus.ACCEPTED.value
        if new_claim.last_verified is None:
            new_claim.last_verified = date.today()
        old_claim.status = ClaimStatus.SUPERSEDED.value
        old_claim.superseded_by = new_claim.claim_id

        self.save_claim(old_claim)
        self.save_claim(new_claim)
        self._audit(
            "claim.superseded",
            {"old_claim_id": old_claim.claim_id, "new_claim_id": new_claim.claim_id},
        )
        return new_claim

    def detect_conflicts(self, claim: Claim) -> list[Claim]:
        conflicts: list[Claim] = []
        for existing in self.list_claims():
            if existing.claim_id == claim.claim_id:
                continue
            if existing.status_value != ClaimStatus.ACCEPTED.value:
                continue
            if existing.conflict_key != claim.conflict_key:
                continue
            if existing.object == claim.object:
                continue
            if self._is_scoped_complement(existing, claim):
                continue
            conflicts.append(existing)
        return conflicts

    def save_claim(self, claim: Claim) -> None:
        self.store.save(claim)

    def load_claim(self, claim_id: str) -> Claim:
        return self.store.load(claim_id)

    def list_claims(self) -> list[Claim]:
        return self.store.list()

    def claim_path(self, claim_id: str) -> Path:
        return self.store.claim_path(claim_id)

    def _audit(self, event: str, payload: dict[str, object]) -> None:
        if self.audit_log:
            self.audit_log.append(event, payload)

    def _is_scoped_complement(self, existing: Claim, incoming: Claim) -> bool:
        if existing.qualifier is None or incoming.qualifier is None:
            return False
        return existing.qualifier != incoming.qualifier
