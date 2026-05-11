from __future__ import annotations

from datetime import date
from pathlib import Path

from pks.kernel.claim.store import ClaimStore
from pks.models import (
    Claim,
    ClaimStatus,
    DomainPolicy,
    EvidenceSourceType,
    MinSupportStatus,
)


class ClaimEngine:
    def __init__(
        self,
        capsule_path: Path,
        store: ClaimStore | None = None,
        policy: DomainPolicy | None = None,
    ) -> None:
        self.capsule_path = capsule_path
        self.store = store or ClaimStore(capsule_path)
        self.policy = policy

    def accept_claim(self, claim_id: str, today: date | None = None) -> Claim:
        claim = self.load_claim(claim_id)
        self.require_min_support(claim)
        conflicts = self.detect_conflicts(claim)
        if conflicts:
            claim.status = ClaimStatus.DISPUTED.value
            self.save_claim(claim)
            for conflict in conflicts:
                conflict.status = ClaimStatus.DISPUTED.value
                self.save_claim(conflict)
            return claim

        claim.status = ClaimStatus.ACCEPTED.value
        if claim.last_verified is None:
            claim.last_verified = today or date.today()
        self.save_claim(claim)
        return claim

    def expire_claim(self, claim_id: str) -> Claim:
        claim = self.load_claim(claim_id)
        claim.status = ClaimStatus.EXPIRED.value
        self.save_claim(claim)
        return claim

    def mark_claim_disputed(self, claim_id: str) -> Claim:
        claim = self.load_claim(claim_id)
        claim.status = ClaimStatus.DISPUTED.value
        self.save_claim(claim)
        return claim

    def supersede_claim(self, old_claim_id: str, new_claim: Claim) -> Claim:
        old_claim = self.load_claim(old_claim_id)
        if old_claim.conflict_key != new_claim.conflict_key:
            raise ValueError("superseding claims must share the same subject and predicate")
        self.require_min_support(new_claim)

        new_claim.supersedes = old_claim.claim_id
        new_claim.status = ClaimStatus.ACCEPTED.value
        if new_claim.last_verified is None:
            new_claim.last_verified = date.today()
        old_claim.status = ClaimStatus.SUPERSEDED.value
        old_claim.superseded_by = new_claim.claim_id

        self.save_claim(old_claim)
        self.save_claim(new_claim)
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

    def validate_min_support(
        self,
        claim: Claim,
        policy: DomainPolicy | None = None,
    ) -> MinSupportStatus:
        policy = policy or self.policy
        if policy is None:
            return MinSupportStatus(passed=True)

        details: list[str] = []
        rule = policy.min_support_for(claim.type_value)

        if len(claim.evidence) < rule.evidence:
            details.append(
                f"{claim.type_value} requires at least {rule.evidence} evidence item(s)"
            )

        if len(claim.supporting_claims) < rule.supporting_claims:
            details.append(
                f"{claim.type_value} requires at least "
                f"{rule.supporting_claims} supporting claim(s)"
            )

        total_support = len(claim.evidence) + len(claim.supporting_claims)
        if total_support < rule.evidence_or_claims_min:
            details.append(
                f"{claim.type_value} requires total support >= {rule.evidence_or_claims_min}"
            )

        accepted_claims = {item.claim_id: item for item in self.list_claims()}
        for supporting_claim in claim.supporting_claims:
            referenced = accepted_claims.get(supporting_claim.claim_id)
            if referenced is None:
                details.append(f"supporting claim not accepted: {supporting_claim.claim_id}")
                continue
            if referenced.status_value != ClaimStatus.ACCEPTED.value:
                details.append(f"supporting claim is not accepted: {supporting_claim.claim_id}")
                continue
            if referenced.type_value not in rule.allowed_support_types:
                details.append(
                    f"{claim.type_value} cannot cite {referenced.type_value} "
                    f"support {supporting_claim.claim_id}"
                )

        if rule.requires_human_source:
            human_sources = {
                EvidenceSourceType.MANUAL.value,
                EvidenceSourceType.CONVERSATION.value,
            }
            if not any(evidence.source_type_value in human_sources for evidence in claim.evidence):
                details.append(f"{claim.type_value} requires manual or conversation evidence")

        return MinSupportStatus(passed=not details, details=details)

    def require_min_support(self, claim: Claim) -> None:
        status = self.validate_min_support(claim)
        if not status.passed:
            raise ValueError("; ".join(status.details))

    def save_claim(self, claim: Claim) -> None:
        self.store.save(claim)

    def load_claim(self, claim_id: str) -> Claim:
        return self.store.load(claim_id)

    def list_claims(
        self,
        *,
        status: str | None = None,
        type: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        subject: str | None = None,
        predicate: str | None = None,
    ) -> list[Claim]:
        claims = self.store.list()
        if status:
            claims = [claim for claim in claims if claim.status_value == status]
        if type:
            claims = [claim for claim in claims if claim.type_value == type]
        if domain:
            claims = [claim for claim in claims if claim.domain_value == domain]
        if tag:
            claims = [claim for claim in claims if tag in claim.tags]
        if subject:
            claims = [claim for claim in claims if claim.subject == subject]
        if predicate:
            claims = [claim for claim in claims if claim.predicate == predicate]
        return claims

    def claim_path(self, claim_id: str) -> Path:
        return self.store.claim_path(claim_id)

    def _is_scoped_complement(self, existing: Claim, incoming: Claim) -> bool:
        if existing.qualifier is None or incoming.qualifier is None:
            return False
        return existing.qualifier != incoming.qualifier
