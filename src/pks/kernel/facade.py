from __future__ import annotations

from datetime import date
from pathlib import Path

from pks.kernel.audit import AuditLog
from pks.kernel.capsule import ProjectRegistry
from pks.kernel.claim import ClaimEngine
from pks.kernel.render import ContextEngine, ProjectionEngine
from pks.kernel.review import ReviewStrategy
from pks.kernel.snapshot import SnapshotManager
from pks.kernel.tracking import ProjectTracker
from pks.models import (
    CapsuleResolution,
    Claim,
    ClaimHealth,
    ClaimStatus,
    DomainPolicy,
    EvidenceIssue,
    HealthReport,
    ProjectMetadata,
    ReviewAction,
    ReviewDecision,
    SnapshotRecord,
)


class Kernel:
    def __init__(self, home: Path | None = None) -> None:
        self.registry = ProjectRegistry(home)
        self.tracker = ProjectTracker()
        self.context_engine = ContextEngine()
        self.projection_engine = ProjectionEngine()

    @property
    def home(self) -> Path:
        return self.registry.home

    def init_home(self) -> None:
        self.registry.ensure_home()

    def create_capsule(self, project: ProjectMetadata) -> Path:
        capsule_path = self.registry.create_capsule(project)
        AuditLog(capsule_path).append("capsule.created", {"project_id": project.project_id})
        return capsule_path

    def load_capsule(self, project_id: str) -> ProjectMetadata:
        return self.registry.load_project(project_id)

    def update_capsule(self, project_id: str, **updates: object) -> ProjectMetadata:
        project = self.registry.update_project(project_id, **updates)
        AuditLog(self.registry.capsule_path(project_id)).append(
            "capsule.updated",
            {"project_id": project_id, "fields": sorted(updates.keys())},
        )
        return project

    def resolve_capsule(self, project_id: str) -> CapsuleResolution:
        return self.registry.resolve_project(project_id)

    def list_capsules(self) -> list[ProjectMetadata]:
        return self.registry.list_projects()

    def generate_pks_new_params(self, **kwargs: object) -> ProjectMetadata:
        return ProjectMetadata.model_validate(kwargs)

    def submit_claim(self, project_id: str, claim: Claim) -> ReviewDecision:
        project = self.load_capsule(project_id)
        claim.project = project.project_id
        claim.domain = project.domain_value

        engine = self._claim_engine(project_id)
        conflicts = engine.detect_conflicts(claim)
        policy = self.registry.load_policy(project.domain)
        decision = ReviewStrategy(policy).decide(claim, [item.claim_id for item in conflicts])

        if decision.action == ReviewAction.REJECT:
            AuditLog(self.registry.capsule_path(project_id)).append(
                "claim.rejected",
                {"claim_id": claim.claim_id, "reason": decision.reason},
            )
            return decision

        engine.submit_claim(claim)
        if decision.action == ReviewAction.AUTO_ACCEPT:
            engine.accept_claim(claim.claim_id)
        return decision

    def accept_claim(self, project_id: str, claim_id: str) -> Claim:
        return self._claim_engine(project_id).accept_claim(claim_id)

    def load_claim(self, project_id: str, claim_id: str) -> Claim:
        return self._claim_engine(project_id).load_claim(claim_id)

    def expire_claim(self, project_id: str, claim_id: str) -> Claim:
        return self._claim_engine(project_id).expire_claim(claim_id)

    def supersede_claim(self, project_id: str, old_claim_id: str, new_claim: Claim) -> Claim:
        project = self.load_capsule(project_id)
        new_claim.project = project.project_id
        new_claim.domain = project.domain_value
        return self._claim_engine(project_id).supersede_claim(old_claim_id, new_claim)

    def mark_claim_stale(self, project_id: str, claim_id: str) -> ClaimHealth:
        for claim_health in self.health_check(project_id).claims:
            if claim_health.claim_id == claim_id:
                AuditLog(self.registry.capsule_path(project_id)).append(
                    "claim.stale_checked",
                    {"claim_id": claim_id, "stale": claim_health.stale},
                )
                return claim_health
        raise FileNotFoundError(f"claim not found: {claim_id}")

    def mark_claim_disputed(self, project_id: str, claim_id: str) -> Claim:
        return self._claim_engine(project_id).mark_claim_disputed(claim_id)

    def list_claims(self, project_id: str) -> list[Claim]:
        return self._claim_engine(project_id).list_claims()

    def check_evidence(self, project_id: str) -> list[EvidenceIssue]:
        project = self.load_capsule(project_id)
        return self.tracker.check_evidence(project, self.list_claims(project_id))

    def health_check(self, project_id: str, today: date | None = None) -> HealthReport:
        today = today or date.today()
        project = self.load_capsule(project_id)
        claims = self.list_claims(project_id)
        policy = self.registry.load_policy(project.domain)
        evidence_issues = self.tracker.check_evidence(project, claims)
        issues_by_claim: dict[str, list[EvidenceIssue]] = {}
        for issue in evidence_issues:
            issues_by_claim.setdefault(issue.claim_id, []).append(issue)

        report = HealthReport(
            project_id=project_id,
            total_claims=len(claims),
            evidence_issues=evidence_issues,
        )

        for claim in claims:
            status = claim.status_value
            if status == ClaimStatus.ACCEPTED.value:
                report.accepted += 1
            elif status == ClaimStatus.CANDIDATE.value:
                report.candidate += 1
            elif status == ClaimStatus.DISPUTED.value:
                report.disputed += 1
            elif status == ClaimStatus.SUPERSEDED.value:
                report.superseded += 1
            elif status == ClaimStatus.EXPIRED.value:
                report.expired += 1

            expired = claim.valid_until is not None and claim.valid_until < today
            stale = self._is_stale(claim, today, issues_by_claim.get(claim.claim_id, []), policy)
            if expired and status != ClaimStatus.EXPIRED.value:
                report.expired += 1
            if stale:
                report.stale += 1

            report.claims.append(
                ClaimHealth(
                    claim_id=claim.claim_id,
                    stale=stale,
                    expired=expired or status == ClaimStatus.EXPIRED.value,
                    evidence_issues=issues_by_claim.get(claim.claim_id, []),
                )
            )

        return report

    def sync_project(self, project_id: str) -> dict[str, object]:
        project = self.load_capsule(project_id)
        result = self.tracker.sync_project(project, self.list_claims(project_id))
        current_commit = result.get("current_commit")
        if isinstance(current_commit, str) and current_commit:
            project.tracking.last_synced_commit = current_commit
            self.registry.save_project(project)
        return result

    def create_snapshot(self, message: str) -> SnapshotRecord:
        self.registry.ensure_home()
        return SnapshotManager(self.home).create_snapshot(message)

    def list_snapshots(self) -> list[SnapshotRecord]:
        return SnapshotManager(self.home).list_snapshots()

    def render_context(self, project_id: str) -> str:
        project = self.load_capsule(project_id)
        claims = self._context_claims(project_id, project)
        stale_claim_ids = self._stale_claim_ids_for(project, claims)
        return self.context_engine.render_markdown(
            project,
            claims,
            capsule_path=self.registry.capsule_path(project_id),
            stale_claim_ids=stale_claim_ids,
        )

    def render_projection(self, project_id: str, write: bool = False) -> str | Path:
        project = self.load_capsule(project_id)
        claims = self._context_claims(project_id, project)
        capsule_path = self.registry.capsule_path(project_id)
        stale_claim_ids = self._stale_claim_ids_for(project, claims)
        if write:
            return self.projection_engine.write_projection(
                project,
                claims,
                capsule_path,
                stale_claim_ids,
            )
        return self.projection_engine.render_markdown(
            project,
            claims,
            capsule_path,
            stale_claim_ids,
        )

    def _claim_engine(self, project_id: str) -> ClaimEngine:
        capsule_path = self.registry.capsule_path(project_id)
        return ClaimEngine(capsule_path, AuditLog(capsule_path))

    def _context_claims(self, project_id: str, project: ProjectMetadata) -> list[Claim]:
        return self.list_claims(project_id) + self.registry.list_taste_claims(project.domain)

    def _stale_claim_ids_for(self, project: ProjectMetadata, claims: list[Claim]) -> set[str]:
        policy = self.registry.load_policy(project.domain)
        evidence_issues = self.tracker.check_evidence(project, claims)
        issues_by_claim: dict[str, list[EvidenceIssue]] = {}
        for issue in evidence_issues:
            issues_by_claim.setdefault(issue.claim_id, []).append(issue)
        return {
            claim.claim_id
            for claim in claims
            if self._is_stale(
                claim,
                date.today(),
                issues_by_claim.get(claim.claim_id, []),
                policy,
            )
        }

    def _is_stale(
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
