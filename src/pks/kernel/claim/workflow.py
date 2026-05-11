from __future__ import annotations

from pks.kernel.audit import AuditClaimFactory
from pks.kernel.candidate import CandidateQueue
from pks.kernel.capsule import ProjectRegistry
from pks.kernel.claim.engine import ClaimEngine
from pks.kernel.review import ReviewEngine, ReviewStrategy
from pks.models import (
    Claim,
    ClaimStatus,
    ProjectMetadata,
    ReviewAction,
    ReviewDecision,
)


class ClaimWorkflow:
    def __init__(self, registry: ProjectRegistry) -> None:
        self.registry = registry

    def submit_candidate(self, project_id: str, claim: Claim) -> ReviewDecision:
        project = self.registry.load_project(project_id)
        claim.project = project.project_id
        claim.domain = project.domain_value
        claim.status = ClaimStatus.CANDIDATE.value
        engine = self.claim_engine(project_id)
        min_support_status = engine.validate_min_support(claim)
        conflicts = engine.detect_conflicts(claim)
        decision = ReviewStrategy(self.registry.load_policy(project.domain)).decide(
            claim,
            [item.claim_id for item in conflicts],
            min_support_status,
        )
        if decision.action != ReviewAction.REJECT:
            self.candidate_queue(project_id).submit(claim)
        else:
            self.audit_factory(project).record(
                project,
                "candidate.reject",
                subject=f"candidate {claim.claim_id}",
                predicate="was_rejected_by",
                object_="kernel",
                payload={"candidate_id": claim.claim_id, "reason": decision.reason},
            )
        return decision

    def list_candidates(self, project_id: str) -> list[Claim]:
        return self.candidate_queue(project_id).list()

    def load_candidate(self, project_id: str, candidate_id: str) -> Claim:
        return self.candidate_queue(project_id).load(candidate_id)

    def delete_candidate(self, project_id: str, candidate_id: str) -> None:
        self.candidate_queue(project_id).delete(candidate_id)

    def review_candidate(self, project_id: str, candidate_id: str) -> ReviewDecision:
        return self.review_engine(project_id).review_candidate(candidate_id)

    def accept_candidate(self, project_id: str, candidate_id: str) -> Claim:
        return self.review_engine(project_id).accept_candidate(candidate_id)

    def reject_candidate(self, project_id: str, candidate_id: str) -> Claim:
        return self.review_engine(project_id).reject_candidate(candidate_id)

    def accept_claim(self, project_id: str, claim_id: str) -> Claim:
        project = self.registry.load_project(project_id)
        claim = self.claim_engine(project_id).accept_claim(claim_id)
        self.record_lifecycle_audit(project, "claim.accept", claim.claim_id, "was_accepted_by")
        return claim

    def load_claim(self, project_id: str, claim_id: str) -> Claim:
        return self.claim_engine(project_id).load_claim(claim_id)

    def expire_claim(self, project_id: str, claim_id: str) -> Claim:
        project = self.registry.load_project(project_id)
        claim = self.claim_engine(project_id).expire_claim(claim_id)
        self.record_lifecycle_audit(project, "claim.expire", claim.claim_id, "was_expired_by")
        return claim

    def supersede_claim(self, project_id: str, old_claim_id: str, new_claim: Claim) -> Claim:
        project = self.registry.load_project(project_id)
        new_claim.project = project.project_id
        new_claim.domain = project.domain_value
        claim = self.claim_engine(project_id).supersede_claim(old_claim_id, new_claim)
        self.audit_factory(project).record(
            project,
            "claim.supersede",
            subject=f"claim {old_claim_id}",
            predicate="was_superseded_by",
            object_=claim.claim_id,
            payload={"old_claim_id": old_claim_id, "new_claim_id": claim.claim_id},
        )
        return claim

    def mark_claim_disputed(self, project_id: str, claim_id: str) -> Claim:
        project = self.registry.load_project(project_id)
        claim = self.claim_engine(project_id).mark_claim_disputed(claim_id)
        self.record_lifecycle_audit(project, "claim.dispute", claim.claim_id, "was_disputed_by")
        return claim

    def list_claims(
        self,
        project_id: str,
        *,
        status: str | None = None,
        type: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        subject: str | None = None,
        predicate: str | None = None,
    ) -> list[Claim]:
        return self.claim_engine(project_id).list_claims(
            status=status,
            type=type,
            domain=domain,
            tag=tag,
            subject=subject,
            predicate=predicate,
        )

    def save_taste_claim(self, claim: Claim, capsule_type: str | None = None) -> Claim:
        if claim.status_value != ClaimStatus.ACCEPTED.value:
            raise ValueError("TasteAndStyle claims must be accepted before injection")
        self.registry.save_taste_claim(claim, capsule_type=capsule_type)
        return claim

    def claim_engine(self, project_id: str) -> ClaimEngine:
        project = self.registry.load_project(project_id)
        return ClaimEngine(
            self.registry.capsule_path(project_id),
            policy=self.registry.load_policy(project.domain),
        )

    def candidate_queue(self, project_id: str) -> CandidateQueue:
        return CandidateQueue(self.registry.capsule_path(project_id))

    def review_engine(self, project_id: str) -> ReviewEngine:
        project = self.registry.load_project(project_id)
        policy = self.registry.load_policy(project.domain)
        return ReviewEngine(
            self.registry.capsule_path(project_id),
            project,
            self.candidate_queue(project_id),
            self.claim_engine(project_id),
            ReviewStrategy(policy),
            self.audit_factory(project),
        )

    def audit_factory(self, project: ProjectMetadata) -> AuditClaimFactory:
        return AuditClaimFactory(
            self.registry.capsule_path(project.project_id),
            self.registry.next_claim_id,
        )

    def record_lifecycle_audit(
        self,
        project: ProjectMetadata,
        event: str,
        claim_id: str,
        predicate: str,
    ) -> None:
        self.audit_factory(project).record(
            project,
            event,
            subject=f"claim {claim_id}",
            predicate=predicate,
            object_="kernel",
            payload={"claim_id": claim_id},
        )
