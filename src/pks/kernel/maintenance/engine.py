from __future__ import annotations

from datetime import UTC, date, datetime

from pks.kernel.audit import AuditClaimFactory
from pks.kernel.capsule import ProjectRegistry
from pks.kernel.claim import ClaimEngine
from pks.kernel.health import HealthEngine
from pks.kernel.tracking import ProjectTracker
from pks.models import Claim, ClaimHealth, ClaimStatus, EvidenceIssue, MaintenanceReport


class MaintenanceEngine:
    def __init__(self, registry: ProjectRegistry, tracker: ProjectTracker) -> None:
        self.registry = registry
        self.tracker = tracker
        self.health = HealthEngine(registry, tracker)

    def run_all(self, project_id: str, today: date | None = None) -> MaintenanceReport:
        return self.run(project_id, today=today)

    def run(
        self,
        project_id: str,
        *,
        today: date | None = None,
        stale: bool = True,
        expiry: bool = True,
        evidence: bool = True,
    ) -> MaintenanceReport:
        if evidence:
            self.sync_sources(project_id)
        stale_claims = self.scan_stale(project_id, today) if stale else []
        expired_claims = self.enforce_expiry(project_id, today) if expiry else []
        evidence_issues = self.recheck_evidence(project_id) if evidence else []
        health = self.health.health_check(project_id, today)
        return MaintenanceReport(
            project_id=project_id,
            stale_found=len(stale_claims),
            expired_enforced=len(expired_claims),
            evidence_issues_found=len(evidence_issues),
            reverification_needed=health.reverification_needed,
            reverification_issues=health.reverification_issues,
            projections_refreshed=False,
        )

    def scan_stale(self, project_id: str, today: date | None = None) -> list[ClaimHealth]:
        return [
            claim
            for claim in self.health.health_check(project_id, today).claims
            if claim.stale
        ]

    def enforce_expiry(self, project_id: str, today: date | None = None) -> list[Claim]:
        today = today or date.today()
        project = self.registry.load_project(project_id)
        engine = self.claim_engine(project_id)
        expired: list[Claim] = []
        for claim in engine.list_claims(status=ClaimStatus.ACCEPTED.value):
            if claim.valid_until is None or claim.valid_until >= today:
                continue
            updated = engine.expire_claim(claim.claim_id)
            self.audit_factory(project).record(
                project,
                "claim.expire",
                subject=f"claim {updated.claim_id}",
                predicate="was_expired_by",
                object_="kernel",
                payload={"claim_id": updated.claim_id},
            )
            expired.append(updated)
        return expired

    def recheck_evidence(self, project_id: str) -> list[EvidenceIssue]:
        project = self.registry.load_project(project_id)
        return self.tracker.check_evidence(project, self.claim_engine(project_id).list_claims())

    def sync_sources(self, project_id: str) -> dict[str, object]:
        project = self.registry.load_project(project_id)
        result = self.tracker.sync_project(project, self.claim_engine(project_id).list_claims())
        current_commit = result.get("current_commit")
        if not isinstance(current_commit, str) or not current_commit:
            return result
        project.tracking.last_synced_commit = current_commit
        project.tracking.last_synced_at = self._datetime_from_result(result.get("synced_at"))
        changed_paths = result.get("changed_paths")
        if isinstance(changed_paths, list) and changed_paths:
            project.tracking.last_changed_paths = [str(path) for path in changed_paths]
            project.tracking.last_change_detected_at = self._datetime_from_result(
                result.get("changed_at")
            )
        self.registry.save_project(project)
        return result

    def claim_engine(self, project_id: str) -> ClaimEngine:
        project = self.registry.load_project(project_id)
        return ClaimEngine(
            self.registry.capsule_path(project_id),
            policy=self.registry.load_policy(project.domain),
        )

    def audit_factory(self, project) -> AuditClaimFactory:
        return AuditClaimFactory(
            self.registry.capsule_path(project.project_id),
            self.registry.next_claim_id,
        )

    def _datetime_from_result(self, value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.now(UTC)
