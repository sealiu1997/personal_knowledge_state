from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from pks.kernel.audit import AuditClaimFactory
from pks.kernel.candidate import CandidateQueue
from pks.kernel.capsule import ProjectRegistry
from pks.kernel.claim import ClaimEngine
from pks.kernel.render import ContextEngine, ProjectionEngine
from pks.kernel.render.projection import claim_matches_projection
from pks.kernel.review import ReviewEngine, ReviewStrategy
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
    ProjectionSpec,
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
        self._audit_factory(project).record(
            project,
            "capsule.create",
            subject=f"capsule {project.project_id}",
            predicate="was_created_by",
            object_="kernel",
            payload={"project_id": project.project_id},
        )
        self.render_projection(project.project_id, write=True)
        return capsule_path

    def load_capsule(self, project_id: str) -> ProjectMetadata:
        return self.registry.load_project(project_id)

    def update_capsule(self, project_id: str, **updates: object) -> ProjectMetadata:
        project = self.registry.update_project(project_id, **updates)
        self._audit_factory(project).record(
            project,
            "capsule.update",
            subject=f"capsule {project_id}",
            predicate="was_updated_by",
            object_="kernel",
            payload={"project_id": project_id, "fields": ",".join(sorted(updates.keys()))},
        )
        return project

    def resolve_capsule(self, project_id: str) -> CapsuleResolution:
        return self.registry.resolve_project(project_id)

    def list_capsules(self) -> list[ProjectMetadata]:
        return self.registry.list_projects()

    def generate_pks_new_params(self, **kwargs: object) -> ProjectMetadata:
        return ProjectMetadata.model_validate(kwargs)

    def submit_claim(self, project_id: str, claim: Claim) -> ReviewDecision:
        return self.submit_candidate(project_id, claim)

    def submit_candidate(self, project_id: str, claim: Claim) -> ReviewDecision:
        project = self.load_capsule(project_id)
        claim.project = project.project_id
        claim.domain = project.domain_value
        claim.status = ClaimStatus.CANDIDATE.value

        engine = self._claim_engine(project_id)
        min_support_status = engine.validate_min_support(claim)
        conflicts = engine.detect_conflicts(claim)
        policy = self.registry.load_policy(project.domain)
        decision = ReviewStrategy(policy).decide(
            claim,
            [item.claim_id for item in conflicts],
            min_support_status,
        )

        if decision.action != ReviewAction.REJECT:
            self._candidate_queue(project_id).submit(claim)
        else:
            self._audit_factory(project).record(
                project,
                "candidate.reject",
                subject=f"candidate {claim.claim_id}",
                predicate="was_rejected_by",
                object_="kernel",
                payload={"candidate_id": claim.claim_id, "reason": decision.reason},
            )
        return decision

    def list_candidates(self, project_id: str) -> list[Claim]:
        return self._candidate_queue(project_id).list()

    def load_candidate(self, project_id: str, candidate_id: str) -> Claim:
        return self._candidate_queue(project_id).load(candidate_id)

    def delete_candidate(self, project_id: str, candidate_id: str) -> None:
        self._candidate_queue(project_id).delete(candidate_id)

    def review_candidate(self, project_id: str, candidate_id: str) -> ReviewDecision:
        return self._review_engine(project_id).review_candidate(candidate_id)

    def accept_candidate(self, project_id: str, candidate_id: str) -> Claim:
        accepted = self._review_engine(project_id).accept_candidate(candidate_id)
        self.render_projection(project_id, write=True)
        return accepted

    def reject_candidate(self, project_id: str, candidate_id: str) -> Claim:
        audit_claim = self._review_engine(project_id).reject_candidate(candidate_id)
        self.render_projection(project_id, write=True)
        return audit_claim

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
        project = self.load_capsule(project_id)
        for claim_health in self.health_check(project_id).claims:
            if claim_health.claim_id == claim_id:
                self._audit_factory(project).record(
                    project,
                    "claim.stale_check",
                    subject=f"claim {claim_id}",
                    predicate="was_checked_for",
                    object_="staleness",
                    payload={"claim_id": claim_id, "stale": claim_health.stale},
                )
                return claim_health
        raise FileNotFoundError(f"claim not found: {claim_id}")

    def mark_claim_disputed(self, project_id: str, claim_id: str) -> Claim:
        return self._claim_engine(project_id).mark_claim_disputed(claim_id)

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
        return self._claim_engine(project_id).list_claims(
            status=status,
            type=type,
            domain=domain,
            tag=tag,
            subject=subject,
            predicate=predicate,
        )

    def check_evidence(self, project_id: str) -> list[EvidenceIssue]:
        project = self.load_capsule(project_id)
        return self.tracker.check_evidence(project, self.list_claims(project_id))

    def health_check(self, project_id: str, today: date | None = None) -> HealthReport:
        today = today or date.today()
        project = self.load_capsule(project_id)
        claims = self.list_claims(project_id)
        candidates = self.list_candidates(project_id)
        policy = self.registry.load_policy(project.domain)
        evidence_issues = self.tracker.check_evidence(project, claims)
        issues_by_claim: dict[str, list[EvidenceIssue]] = {}
        for issue in evidence_issues:
            issues_by_claim.setdefault(issue.claim_id, []).append(issue)

        report = HealthReport(
            project_id=project_id,
            total_claims=len(claims) + len(candidates),
            evidence_issues=evidence_issues,
        )
        report.candidate = len(candidates)

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
            min_support_status = self._claim_engine(project_id).validate_min_support(claim, policy)
            if not min_support_status.passed:
                report.min_support_violations += 1
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
                    min_support_issues=min_support_status.details,
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
            self._audit_factory(project).record(
                project,
                "project.sync",
                subject=f"project {project_id}",
                predicate="was_synced_at",
                object_=current_commit,
                payload={"project_id": project_id, "current_commit": current_commit},
            )
        return result

    def create_snapshot(self, message: str) -> SnapshotRecord:
        self.registry.ensure_home()
        should_record_audit = self._snapshot_has_changes()
        if should_record_audit:
            for project in self.list_capsules():
                self._audit_factory(project).record(
                    project,
                    "snapshot.create",
                    subject=f"snapshot request for {project.project_id}",
                    predicate="was_requested_by",
                    object_="kernel",
                    payload={"message": message},
                )
        snapshot = SnapshotManager(self.home).create_snapshot(message)
        return snapshot

    def list_snapshots(self) -> list[SnapshotRecord]:
        return SnapshotManager(self.home).list_snapshots()

    def render_context(self, project_id: str) -> str:
        project = self.load_capsule(project_id)
        claims = self._context_claims(project_id, project)
        stale_claim_ids = self._stale_claim_ids_for(project, claims)
        return self.projection_engine.render_markdown(
            project,
            claims,
            capsule_path=self.registry.capsule_path(project_id),
            specs=self.list_projections(project_id),
            stale_claim_ids=stale_claim_ids,
        )

    def render_projection(
        self,
        project_id: str,
        projection_id: str | None = None,
        write: bool = False,
    ) -> str | Path:
        project = self.load_capsule(project_id)
        claims = self._context_claims(project_id, project)
        capsule_path = self.registry.capsule_path(project_id)
        stale_claim_ids = self._stale_claim_ids_for(project, claims)
        specs = self.list_projections(project_id)
        if projection_id:
            spec = self._projection_spec(project, projection_id)
            if write:
                return self.projection_engine.write_capsule_projection(
                    capsule_path,
                    spec,
                    claims,
                    stale_claim_ids,
                )
            return self.projection_engine.render_projection(spec, claims, stale_claim_ids)
        if write:
            for spec in specs:
                self.projection_engine.write_capsule_projection(
                    capsule_path,
                    spec,
                    claims,
                    stale_claim_ids,
                )
            if project.project_root() is None:
                return self.projection_engine.render_markdown(
                    project,
                    claims,
                    capsule_path,
                    specs,
                    stale_claim_ids,
                )
            return self.projection_engine.write_projection(
                project,
                claims,
                capsule_path,
                specs,
                stale_claim_ids,
            )
        return self.projection_engine.render_markdown(
            project,
            claims,
            capsule_path,
            specs,
            stale_claim_ids,
        )

    def list_projections(self, project_id: str) -> list[ProjectionSpec]:
        project = self.load_capsule(project_id)
        return self.registry.list_projection_specs(project.capsule_type)

    def submit_projection_claim(
        self,
        project_id: str,
        projection_id: str,
        claim_draft: Claim,
    ) -> ReviewDecision:
        project = self.load_capsule(project_id)
        spec = self._projection_spec(project, projection_id)
        claim_draft.tags = sorted(set(claim_draft.tags).union(spec.filters.tags))
        return self.submit_candidate(project_id, claim_draft)

    def patch_projection_claim(
        self,
        project_id: str,
        projection_id: str,
        claim_id: str,
        changes: dict[str, object],
    ) -> Claim | ReviewDecision:
        project = self.load_capsule(project_id)
        spec = self._projection_spec(project, projection_id)
        claim = self.load_claim(project_id, claim_id)
        stale_claim_ids = self._stale_claim_ids_for(
            project,
            self._context_claims(project_id, project),
        )
        if not claim_matches_projection(claim, spec, stale_claim_ids):
            raise ValueError(f"claim {claim_id} does not belong to projection {projection_id}")
        if "type" in changes:
            raise ValueError("claim type is immutable")

        semantic_fields = {"subject", "predicate", "object"}
        if semantic_fields.intersection(changes):
            data = claim.model_dump(mode="python")
            data.update(changes)
            data["claim_id"] = self.registry.next_claim_id(claim.type_value)
            data["supersedes"] = claim.claim_id
            data["status"] = ClaimStatus.CANDIDATE.value
            candidate = Claim.model_validate(data)
            return self.submit_candidate(project_id, candidate)

        data = claim.model_dump(mode="python")
        data.update(changes)
        updated = Claim.model_validate(data)
        self._claim_engine(project_id).require_min_support(updated)
        self._claim_engine(project_id).save_claim(updated)
        self._audit_factory(project).record(
            project,
            "projection.patch",
            subject=f"claim {claim_id}",
            predicate="was_patched_through",
            object_=projection_id,
            payload={"claim_id": claim_id, "projection_id": projection_id},
        )
        self.render_projection(project_id, projection_id, write=True)
        return updated

    def load_policy(self, domain: str) -> DomainPolicy:
        return self.registry.load_policy(domain)

    def validate_policy(self, domain: str) -> list[str]:
        return self.registry.validate_policy(domain)

    def _claim_engine(self, project_id: str) -> ClaimEngine:
        capsule_path = self.registry.capsule_path(project_id)
        project = self.load_capsule(project_id)
        return ClaimEngine(capsule_path, policy=self.registry.load_policy(project.domain))

    def _candidate_queue(self, project_id: str) -> CandidateQueue:
        return CandidateQueue(self.registry.capsule_path(project_id))

    def _review_engine(self, project_id: str) -> ReviewEngine:
        project = self.load_capsule(project_id)
        policy = self.registry.load_policy(project.domain)
        return ReviewEngine(
            self.registry.capsule_path(project_id),
            project,
            self._candidate_queue(project_id),
            self._claim_engine(project_id),
            ReviewStrategy(policy),
            self._audit_factory(project),
        )

    def _audit_factory(self, project: ProjectMetadata) -> AuditClaimFactory:
        return AuditClaimFactory(
            self.registry.capsule_path(project.project_id),
            self.registry.next_claim_id,
        )

    def _context_claims(self, project_id: str, project: ProjectMetadata) -> list[Claim]:
        return self.list_claims(project_id) + self.registry.list_taste_claims(
            project.domain,
            project.capsule_type,
        )

    def _projection_spec(self, project: ProjectMetadata, projection_id: str) -> ProjectionSpec:
        for spec in self.registry.list_projection_specs(project.capsule_type):
            if spec.projection_id == projection_id:
                return spec
        raise KeyError(f"unknown projection: {projection_id}")

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

    def _snapshot_has_changes(self) -> bool:
        if not (self.home / ".git").exists():
            return True
        completed = subprocess.run(
            ["git", "-C", str(self.home), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
        return bool(completed.stdout.strip())
