from __future__ import annotations

from pks.models import Claim, ClaimType, DomainPolicy, ReviewAction, ReviewDecision


class ReviewStrategy:
    def __init__(self, policy: DomainPolicy) -> None:
        self.policy = policy

    def decide(self, claim: Claim, conflict_ids: list[str] | None = None) -> ReviewDecision:
        conflict_ids = conflict_ids or []
        if not claim.evidence:
            return ReviewDecision(action=ReviewAction.REJECT, reason="missing evidence")
        if claim.confidence < 0.3:
            return ReviewDecision(action=ReviewAction.REJECT, reason="confidence below 0.3")
        if conflict_ids:
            return ReviewDecision(
                action=ReviewAction.MANUAL_REVIEW,
                reason="potential conflict",
                conflicts=conflict_ids,
            )

        if claim.type_value in self.policy.manual_review_types:
            return ReviewDecision(action=ReviewAction.MANUAL_REVIEW, reason="manual review type")

        rule = self.policy.lifecycle_for(claim.type_value)
        if claim.type_value == ClaimType.FACTUAL.value and rule.auto_accept_threshold is not None:
            if claim.confidence >= rule.auto_accept_threshold:
                return ReviewDecision(
                    action=ReviewAction.AUTO_ACCEPT,
                    reason="confidence meets auto-accept threshold",
                )

        return ReviewDecision(
            action=ReviewAction.MANUAL_REVIEW,
            reason="below auto-accept threshold",
        )
