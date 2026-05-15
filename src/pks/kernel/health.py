from __future__ import annotations

from datetime import UTC, date, datetime, time
from pathlib import Path

from pks.kernel.candidate import CandidateQueue
from pks.kernel.capsule import ProjectRegistry
from pks.kernel.claim import ClaimEngine
from pks.kernel.tracking import ProjectTracker
from pks.models import (
    Claim,
    ClaimHealth,
    ClaimStatus,
    DomainPolicy,
    EvidenceIssue,
    HealthReport,
    ReVerificationIssue,
)

BROKEN_SUPPORT_STATUSES = {
    ClaimStatus.SUPERSEDED.value,
    ClaimStatus.EXPIRED.value,
    ClaimStatus.DISPUTED.value,
}


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
        reverification_issues = self.reverification_issues(project_id, today=today)
        reverification_by_claim = {
            issue.claim_id: issue for issue in reverification_issues
        }
        report = HealthReport(
            project_id=project_id,
            total_claims=len(claims) + len(candidates),
            evidence_issues=evidence_issues,
            reverification_needed=len(reverification_issues),
            reverification_issues=reverification_issues,
            candidate=len(candidates),
        )
        for claim in claims:
            self._add_claim_health(
                report,
                project_id,
                claim,
                today,
                policy,
                issues_by_claim,
                reverification_by_claim,
            )
        return report

    def reverification_issues(
        self,
        project_id: str,
        today: date | None = None,
    ) -> list[ReVerificationIssue]:
        project = self.registry.load_project(project_id)
        claims = self.list_claims(project_id)
        claims_by_id = {claim.claim_id: claim for claim in claims}
        accepted_claims = [
            claim for claim in claims if claim.status_value == ClaimStatus.ACCEPTED.value
        ]
        now = datetime.combine(today or date.today(), time.min, tzinfo=UTC)
        issues_by_claim: dict[str, ReVerificationIssue] = {}

        for claim in accepted_claims:
            for support in claim.supporting_claims:
                referenced = claims_by_id.get(support.claim_id)
                if referenced is None or referenced.status_value not in BROKEN_SUPPORT_STATUSES:
                    continue
                detected_at = self._status_trigger_time(referenced, claims_by_id, now)
                if self._verified_after(claim, detected_at):
                    continue
                issues_by_claim.setdefault(
                    claim.claim_id,
                    ReVerificationIssue(
                        claim_id=claim.claim_id,
                        reason="support_chain_broken",
                        trigger_claim_id=referenced.claim_id,
                        detected_at=detected_at,
                    ),
                )

        changed_paths = {
            self._normalize_project_path(path)
            for path in project.tracking.last_changed_paths
            if path.strip()
        }
        changed_paths.discard("")
        changed_at = project.tracking.last_change_detected_at
        if changed_paths and changed_at is not None:
            for claim in accepted_claims:
                if self._verified_after(claim, changed_at):
                    continue
                for evidence in claim.evidence:
                    if self._source_matches_changed_path(
                        project,
                        evidence.source_ref,
                        changed_paths,
                    ):
                        issues_by_claim.setdefault(
                            claim.claim_id,
                            ReVerificationIssue(
                                claim_id=claim.claim_id,
                                reason="evidence_source_changed",
                                trigger_source=evidence.source_ref,
                                detected_at=changed_at,
                            ),
                        )
                        break

        self._propagate_reverification(accepted_claims, issues_by_claim)
        return sorted(issues_by_claim.values(), key=lambda issue: issue.claim_id)

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
        reverification_by_claim: dict[str, ReVerificationIssue],
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
        reverification_issue = reverification_by_claim.get(claim.claim_id)
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
                needs_reverification=reverification_issue is not None,
                reverification_reason=(
                    reverification_issue.reason if reverification_issue is not None else None
                ),
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

    def _propagate_reverification(
        self,
        accepted_claims: list[Claim],
        issues_by_claim: dict[str, ReVerificationIssue],
    ) -> None:
        changed = True
        while changed:
            changed = False
            for claim in accepted_claims:
                if claim.claim_id in issues_by_claim:
                    continue
                for support in claim.supporting_claims:
                    trigger_issue = issues_by_claim.get(support.claim_id)
                    if trigger_issue is None:
                        continue
                    if self._verified_after(claim, trigger_issue.detected_at):
                        continue
                    issues_by_claim[claim.claim_id] = ReVerificationIssue(
                        claim_id=claim.claim_id,
                        reason="cascade_dependency",
                        trigger_claim_id=support.claim_id,
                        trigger_source=trigger_issue.trigger_source,
                        detected_at=trigger_issue.detected_at,
                    )
                    changed = True
                    break

    def _status_trigger_time(
        self,
        claim: Claim,
        claims_by_id: dict[str, Claim],
        fallback: datetime,
    ) -> datetime:
        if claim.status_value == ClaimStatus.SUPERSEDED.value and claim.superseded_by:
            superseding = claims_by_id.get(claim.superseded_by)
            if superseding is not None:
                return self._not_after(superseding.created_at, fallback)
        if claim.valid_until is not None:
            return self._not_after(
                datetime.combine(claim.valid_until, time.min, tzinfo=UTC),
                fallback,
            )
        audit_predicates = {
            ClaimStatus.EXPIRED.value: "was_expired_by",
            ClaimStatus.DISPUTED.value: "was_disputed_by",
            ClaimStatus.SUPERSEDED.value: "was_superseded_by",
        }
        predicate = audit_predicates.get(claim.status_value)
        if predicate:
            audit_times = [
                item.created_at
                for item in claims_by_id.values()
                if "audit" in item.tags
                and item.subject == f"claim {claim.claim_id}"
                and item.predicate == predicate
            ]
            if audit_times:
                return self._not_after(max(audit_times), fallback)
        return self._not_after(claim.created_at or fallback, fallback)

    def _not_after(self, detected_at: datetime, reference: datetime) -> datetime:
        detected_at = self._as_utc(detected_at)
        reference = self._as_utc(reference)
        return detected_at if detected_at <= reference else reference

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _verified_after(self, claim: Claim, detected_at: datetime) -> bool:
        if claim.last_verified is None:
            return False
        return claim.last_verified >= detected_at.date()

    def _source_matches_changed_path(
        self,
        project,
        source_ref: str,
        changed_paths: set[str],
    ) -> bool:
        source = source_ref.split("#", 1)[0].strip()
        if not source:
            return False
        candidates = {self._normalize_project_path(source)}
        source_path = Path(source).expanduser()
        root = project.project_root()
        if source_path.is_absolute() and root is not None:
            try:
                candidates.add(self._normalize_project_path(str(source_path.relative_to(root))))
            except ValueError:
                pass
        return bool(candidates.intersection(changed_paths))

    def _normalize_project_path(self, value: str) -> str:
        return Path(value).as_posix().removeprefix("./")
