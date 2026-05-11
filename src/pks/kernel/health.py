from __future__ import annotations

from datetime import date

from pks.kernel.candidate import CandidateQueue
from pks.kernel.capsule import ProjectRegistry
from pks.kernel.claim import ClaimEngine
from pks.kernel.tracking import ProjectTracker
from pks.models import Claim, ClaimHealth, ClaimStatus, DomainPolicy, EvidenceIssue, HealthReport


class HealthEngine:
    def __init__(self, registry: ProjectRegistry, tracker: ProjectTracker) -> None:
        self.registry = registry
        self.tracker = tracker

    def check_evidence(self, project_id: str) -> list[EvidenceIssue]:
        project = self.registry.load_project(project_id)
        return self.tracker.check_evidence(project, self.list_claims(project_id))

    def health_check(self, project_id: str, today: date | None = None) -> HealthReport:
        today = today or date.today()
        project = self.registry.load_project(project_id)
        claims = self.list_claims(project_id)
        candidates = self.list_candidates(project_id)
        policy = self.registry.load_policy(project.domain)
        evidence_issues = self.tracker.check_evidence(project, claims)
        issues_by_claim = self._issues_by_claim(evidence_issues)
        report = HealthReport(
            project_id=project_id,
            total_claims=len(claims) + len(candidates),
            evidence_issues=evidence_issues,
            candidate=len(candidates),
        )
        for claim in claims:
            self._add_claim_health(report, project_id, claim, today, policy, issues_by_claim)
        return report

    def stale_claim_ids_for(
        self,
        project_id: str,
        claims: list[Claim],
        today: date | None = None,
    ) -> set[str]:
        project = self.registry.load_project(project_id)
        policy = self.registry.load_policy(project.domain)
        issues_by_claim = self._issues_by_claim(self.tracker.check_evidence(project, claims))
        today = today or date.today()
        return {
            claim.claim_id
            for claim in claims
            if self.is_stale(claim, today, issues_by_claim.get(claim.claim_id, []), policy)
        }

    def is_stale(
        self,
        claim: Claim,
        today: date,
        evidence_issues: list[EvidenceIssue],
        policy: DomainPolicy,
    ) -> bool:
        if claim.status_value != ClaimStatus.ACCEPTED.value:
            return False
        if evidence_issues:
            return True
        rule = policy.lifecycle_for(claim.type_value)
        if rule.stale_after_days is None or claim.last_verified is None:
            return False
        return (today - claim.last_verified).days > rule.stale_after_days

    def list_claims(self, project_id: str) -> list[Claim]:
        return self.claim_engine(project_id).list_claims()

    def list_candidates(self, project_id: str) -> list[Claim]:
        return CandidateQueue(self.registry.capsule_path(project_id)).list()

    def claim_engine(self, project_id: str) -> ClaimEngine:
        project = self.registry.load_project(project_id)
        return ClaimEngine(
            self.registry.capsule_path(project_id),
            policy=self.registry.load_policy(project.domain),
        )

    def _add_claim_health(
        self,
        report: HealthReport,
        project_id: str,
        claim: Claim,
        today: date,
        policy: DomainPolicy,
        issues_by_claim: dict[str, list[EvidenceIssue]],
    ) -> None:
        status = claim.status_value
        report.accepted += int(status == ClaimStatus.ACCEPTED.value)
        report.candidate += int(status == ClaimStatus.CANDIDATE.value)
        report.disputed += int(status == ClaimStatus.DISPUTED.value)
        report.superseded += int(status == ClaimStatus.SUPERSEDED.value)
        report.expired += int(status == ClaimStatus.EXPIRED.value)
        expired = claim.valid_until is not None and claim.valid_until < today
        stale = self.is_stale(claim, today, issues_by_claim.get(claim.claim_id, []), policy)
        support = self.claim_engine(project_id).validate_min_support(claim, policy)
        report.expired += int(expired and status != ClaimStatus.EXPIRED.value)
        report.stale += int(stale)
        report.min_support_violations += int(not support.passed)
        report.claims.append(
            ClaimHealth(
                claim_id=claim.claim_id,
                stale=stale,
                expired=expired or status == ClaimStatus.EXPIRED.value,
                evidence_issues=issues_by_claim.get(claim.claim_id, []),
                min_support_issues=support.details,
            )
        )

    def _issues_by_claim(
        self,
        evidence_issues: list[EvidenceIssue],
    ) -> dict[str, list[EvidenceIssue]]:
        issues_by_claim: dict[str, list[EvidenceIssue]] = {}
        for issue in evidence_issues:
            issues_by_claim.setdefault(issue.claim_id, []).append(issue)
        return issues_by_claim
