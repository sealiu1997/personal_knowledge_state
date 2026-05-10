from __future__ import annotations

from pks.models import (
    Claim,
    ClaimType,
    DomainPolicy,
    MinSupportStatus,
    ReviewAction,
    ReviewDecision,
)


class ReviewStrategy:
    def __init__(self, policy: DomainPolicy) -> None:
        self.policy = policy

    def decide(
        self,
        claim: Claim,
        conflict_ids: list[str] | None = None,
        min_support_status: MinSupportStatus | None = None,
    ) -> ReviewDecision:
        conflict_ids = conflict_ids or []
        min_support_status = min_support_status or MinSupportStatus(passed=True)
        policy_notes = [f"policy domain={self.policy.domain}"]

        if not min_support_status.passed:
            return ReviewDecision(
                action=ReviewAction.REJECT,
                reason="min_support failed",
                evidence_issues=min_support_status.details,
                min_support_status=min_support_status,
                policy_notes=policy_notes,
            )
        if claim.confidence < 0.3:
            return ReviewDecision(
                action=ReviewAction.REJECT,
                reason="confidence below 0.3",
                min_support_status=min_support_status,
                policy_notes=policy_notes,
            )
        if conflict_ids:
            return ReviewDecision(
                action=ReviewAction.MANUAL_REVIEW,
                reason="potential conflict",
                conflicts=conflict_ids,
                min_support_status=min_support_status,
                policy_notes=policy_notes,
            )

        if claim.type_value in self.policy.manual_review_types:
            return ReviewDecision(
                action=ReviewAction.MANUAL_REVIEW,
                reason="manual review type",
                min_support_status=min_support_status,
                policy_notes=policy_notes,
            )

        rule = self.policy.lifecycle_for(claim.type_value)
        if claim.type_value == ClaimType.FACTUAL.value and rule.auto_accept_threshold is not None:
            if claim.confidence >= rule.auto_accept_threshold:
                return ReviewDecision(
                    action=ReviewAction.AUTO_ACCEPT,
                    reason="confidence meets auto-accept threshold",
                    min_support_status=min_support_status,
                    policy_notes=policy_notes,
                )

        return ReviewDecision(
            action=ReviewAction.MANUAL_REVIEW,
            reason="below auto-accept threshold",
            min_support_status=min_support_status,
            policy_notes=policy_notes,
        )
