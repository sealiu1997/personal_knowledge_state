from __future__ import annotations

from datetime import date
from pathlib import Path

from pks.kernel.audit import AuditClaimFactory
from pks.kernel.candidate import CandidateQueue
from pks.kernel.claim import ClaimEngine
from pks.kernel.review.strategy import ReviewStrategy
from pks.models import Claim, ClaimStatus, ProjectMetadata, ReviewAction, ReviewDecision


class ReviewEngine:
    def __init__(
        self,
        capsule_path: Path,
        project: ProjectMetadata,
        candidate_queue: CandidateQueue,
        claim_engine: ClaimEngine,
        strategy: ReviewStrategy,
        audit_factory: AuditClaimFactory,
    ) -> None:
        self.capsule_path = capsule_path
        self.project = project
        self.candidate_queue = candidate_queue
        self.claim_engine = claim_engine
        self.strategy = strategy
        self.audit_factory = audit_factory

    def review_candidate(self, candidate_id: str) -> ReviewDecision:
        candidate = self.candidate_queue.load(candidate_id)
        conflicts = self.claim_engine.detect_conflicts(candidate)
        min_support_status = self.claim_engine.validate_min_support(candidate)
        return self.strategy.decide(
            candidate,
            [claim.claim_id for claim in conflicts],
            min_support_status,
        )

    def accept_candidate(self, candidate_id: str) -> Claim:
        candidate = self.candidate_queue.load(candidate_id)
        decision = self.review_candidate(candidate_id)
        if decision.action == ReviewAction.REJECT:
            raise ValueError(f"candidate cannot be accepted: {decision.reason}")

        candidate.status = ClaimStatus.CANDIDATE.value
        self.claim_engine.save_claim(candidate)
        accepted = self.claim_engine.accept_claim(candidate.claim_id, today=date.today())
        self.candidate_queue.delete(candidate_id)
        self.audit_factory.record(
            self.project,
            "review.accept",
            subject=f"candidate {candidate_id}",
            predicate="was_accepted_by",
            object_="human",
            payload={"candidate_id": candidate_id, "action": "accept"},
        )
        return accepted

    def reject_candidate(self, candidate_id: str) -> Claim:
        self.candidate_queue.load(candidate_id)
        self.candidate_queue.delete(candidate_id)
        return self.audit_factory.record(
            self.project,
            "review.reject",
            subject=f"candidate {candidate_id}",
            predicate="was_rejected_by",
            object_="human",
            payload={"candidate_id": candidate_id, "action": "reject"},
        )
