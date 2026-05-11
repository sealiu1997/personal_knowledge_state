from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from pks.kernel.capsule import ProjectRegistry
from pks.kernel.claim.workflow import ClaimWorkflow
from pks.kernel.health import HealthEngine
from pks.kernel.maintenance import MaintenanceEngine
from pks.kernel.render import ProjectionEngine
from pks.kernel.render.projection import claim_matches_projection
from pks.kernel.render.service import ProjectionService
from pks.kernel.snapshot import SnapshotManager
from pks.kernel.storage import read_yaml
from pks.kernel.tracking import ProjectTracker
from pks.models import (
    CapsuleResolution,
    Claim,
    ClaimHealth,
    ClaimStatus,
    ClaimType,
    DomainPolicy,
    HealthReport,
    MaintenanceReport,
    ProjectionIssue,
    ProjectionSpec,
    ProjectMetadata,
    ReviewDecision,
    SnapshotRecord,
    TokenPermission,
)


class KernelMaintenance:
    def __init__(self, engine: MaintenanceEngine, refresh_projections) -> None:
        self.engine = engine
        self.refresh_projections = refresh_projections

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
        report = self.engine.run(
            project_id,
            today=today,
            stale=stale,
            expiry=expiry,
            evidence=evidence,
        )
        if stale or expiry or evidence:
            self.refresh_projections(project_id)
            report.projections_refreshed = True
        return report

    def scan_stale(self, project_id: str, today: date | None = None):
        return self.engine.scan_stale(project_id, today)

    def enforce_expiry(self, project_id: str, today: date | None = None):
        return self.engine.enforce_expiry(project_id, today)

    def recheck_evidence(self, project_id: str):
        return self.engine.recheck_evidence(project_id)


class Kernel:
    def __init__(self, home: Path | None = None) -> None:
        self.registry = ProjectRegistry(home)
        self.tracker = ProjectTracker()
        self.claims = ClaimWorkflow(self.registry)
        self.health = HealthEngine(self.registry, self.tracker)
        self.projections = ProjectionService(
            self.registry,
            ProjectionEngine(),
            self.health,
            self.claims,
        )
        self.maintenance = KernelMaintenance(
            MaintenanceEngine(self.registry, self.tracker),
            self._refresh_projections,
        )

    @property
    def home(self) -> Path:
        return self.registry.home

    def init_home(self) -> None:
        self.registry.ensure_home()

    def create_capsule(self, project: ProjectMetadata) -> Path:
        capsule_path = self.registry.create_capsule(project)
        self.claims.audit_factory(project).record(
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
        self.claims.audit_factory(project).record(
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

    def submit_candidate(self, project_id: str, claim: Claim) -> ReviewDecision:
        return self.claims.submit_candidate(project_id, claim)

    def submit_candidate_draft(
        self,
        project_id: str,
        claim_data: dict[str, object],
    ) -> ReviewDecision:
        return self.submit_candidate(project_id, self.build_candidate_claim(project_id, claim_data))

    def build_candidate_claim(self, project_id: str, claim_data: dict[str, object]) -> Claim:
        project = self.load_capsule(project_id)
        data = dict(claim_data)
        if "object_" in data and "object" not in data:
            data["object"] = data.pop("object_")
        claim_type = data.get("type") or ClaimType.FACTUAL.value
        data["type"] = claim_type
        data["claim_id"] = data.get("claim_id") or self.registry.next_claim_id(str(claim_type))
        data["domain"] = project.domain_value
        data["project"] = project.project_id
        data["status"] = ClaimStatus.CANDIDATE.value
        data.setdefault("created_by", "human")
        data.setdefault("confidence", 1.0)
        data["tags"] = self._normalize_string_list(data.get("tags"))
        data["evidence"] = self._normalize_evidence_list(data.get("evidence"))
        data["supporting_claims"] = self._normalize_supporting_claims(
            data.get("supporting_claims")
        )
        return Claim.model_validate(data)

    def list_candidates(self, project_id: str) -> list[Claim]:
        return self.claims.list_candidates(project_id)

    def load_candidate(self, project_id: str, candidate_id: str) -> Claim:
        return self.claims.load_candidate(project_id, candidate_id)

    def review_candidate(self, project_id: str, candidate_id: str) -> ReviewDecision:
        return self.claims.review_candidate(project_id, candidate_id)

    def accept_candidate(self, project_id: str, candidate_id: str) -> Claim:
        claim = self.claims.accept_candidate(project_id, candidate_id)
        self._refresh_projections(project_id)
        return claim

    def reject_candidate(self, project_id: str, candidate_id: str) -> Claim:
        audit_claim = self.claims.reject_candidate(project_id, candidate_id)
        self._refresh_projections(project_id)
        return audit_claim

    def accept_claim(self, project_id: str, claim_id: str) -> Claim:
        claim = self.claims.accept_claim(project_id, claim_id)
        self._refresh_projections(project_id)
        return claim

    def load_claim(self, project_id: str, claim_id: str) -> Claim:
        return self.claims.load_claim(project_id, claim_id)

    def expire_claim(self, project_id: str, claim_id: str) -> Claim:
        claim = self.claims.expire_claim(project_id, claim_id)
        self._refresh_projections(project_id)
        return claim

    def supersede_claim(self, project_id: str, old_claim_id: str, new_claim: Claim) -> Claim:
        claim = self.claims.supersede_claim(project_id, old_claim_id, new_claim)
        self._refresh_projections(project_id)
        return claim

    def mark_claim_stale(self, project_id: str, claim_id: str) -> ClaimHealth:
        project = self.load_capsule(project_id)
        for claim_health in self.health.health_check(project_id).claims:
            if claim_health.claim_id == claim_id:
                self.claims.audit_factory(project).record(
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
        claim = self.claims.mark_claim_disputed(project_id, claim_id)
        self._refresh_projections(project_id)
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
        projection: str | None = None,
        sort: str | None = None,
    ) -> list[Claim]:
        claims = self.claims.list_claims(
            project_id,
            status=status,
            type=type,
            domain=domain,
            tag=tag,
            subject=subject,
            predicate=predicate,
        )
        if projection:
            spec = self.load_projection_spec(project_id, projection)
            stale_ids = self.health.stale_claim_ids_for(project_id, claims)
            claims = [claim for claim in claims if claim_matches_projection(claim, spec, stale_ids)]
        if sort == "created_desc":
            claims = sorted(claims, key=lambda claim: claim.created_at, reverse=True)
        elif sort == "verified_desc":
            claims = sorted(
                claims,
                key=lambda claim: claim.last_verified or date.min,
                reverse=True,
            )
        else:
            claims = sorted(claims, key=lambda claim: claim.claim_id)
        return claims

    def health_check(self, project_id: str, today: date | None = None) -> HealthReport:
        return self.health.health_check(project_id, today)

    def sync_project(self, project_id: str) -> dict[str, object]:
        project = self.load_capsule(project_id)
        result = self.tracker.sync_project(project, self.list_claims(project_id))
        current_commit = result.get("current_commit")
        if isinstance(current_commit, str) and current_commit:
            project.tracking.last_synced_commit = current_commit
            self.registry.save_project(project)
            self.claims.audit_factory(project).record(
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
        if self._snapshot_has_changes():
            for project in self.list_capsules():
                self.claims.audit_factory(project).record(
                    project,
                    "snapshot.create",
                    subject=f"snapshot request for {project.project_id}",
                    predicate="was_requested_by",
                    object_="kernel",
                    payload={"message": message},
                )
        return SnapshotManager(self.home).create_snapshot(message)

    def list_snapshots(self) -> list[SnapshotRecord]:
        return SnapshotManager(self.home).list_snapshots()

    def render_context(self, project_id: str) -> str:
        return self.projections.render_context(project_id)

    def render_projection(
        self, project_id: str, projection_id: str | None = None, write: bool = False
    ) -> str | Path:
        return self.projections.render_projection(project_id, projection_id, write)

    def preview_projection_spec(
        self,
        project_id: str,
        spec: ProjectionSpec,
    ) -> dict[str, object]:
        return self.projections.preview_projection_spec(project_id, spec)

    def matching_projection_claims(
        self,
        project_id: str,
        spec: ProjectionSpec,
    ) -> list[Claim]:
        return self.projections.matching_claims(project_id, spec)

    def check_projection_integrity(self, project_id: str) -> list[ProjectionIssue]:
        return self.projections.check_integrity(project_id)

    def list_projections(self, project_id: str) -> list[ProjectionSpec]:
        return self.projections.list_projections(project_id)

    def list_custom_projection_ids(self, project_id: str) -> set[str]:
        return self.projections.list_custom_projection_ids(project_id)

    def load_projection_spec(self, project_id: str, projection_id: str) -> ProjectionSpec:
        return self.projections.load_projection_spec(project_id, projection_id)

    def create_projection_spec(self, project_id: str, spec: ProjectionSpec) -> ProjectionSpec:
        return self.projections.create_projection_spec(project_id, spec)

    def update_projection_spec(
        self, project_id: str, projection_id: str, changes: dict[str, object]
    ) -> ProjectionSpec:
        return self.projections.update_projection_spec(project_id, projection_id, changes)

    def delete_projection_spec(self, project_id: str, projection_id: str) -> None:
        self.projections.delete_projection_spec(project_id, projection_id)

    def save_taste_claim(self, claim: Claim, capsule_type: str | None = None) -> Claim:
        return self.claims.save_taste_claim(claim, capsule_type)

    def submit_projection_claim(
        self, project_id: str, projection_id: str, claim_draft: Claim
    ) -> ReviewDecision:
        return self.projections.submit_projection_claim(project_id, projection_id, claim_draft)

    def patch_projection_claim(
        self, project_id: str, projection_id: str, claim_id: str, changes: dict[str, object]
    ) -> Claim | ReviewDecision:
        return self.projections.patch_projection_claim(project_id, projection_id, claim_id, changes)

    def load_policy(self, domain: str) -> DomainPolicy:
        return self.registry.load_policy(domain)

    def update_policy(self, domain: str, policy_data: dict[str, object]) -> DomainPolicy:
        data = dict(policy_data)
        data["domain"] = domain
        policy = DomainPolicy.model_validate(data)
        saved = self.registry.save_policy(policy)
        return saved

    def validate_policy(self, domain: str) -> list[str]:
        return self.registry.validate_policy(domain)

    def validate_token(self, token_hash: str) -> TokenPermission:
        config_path = self.home / "config.yaml"
        if not config_path.exists():
            return TokenPermission.INVALID
        tokens = read_yaml(config_path).get("mcp_tokens") or []
        if not isinstance(tokens, list):
            return TokenPermission.INVALID
        for record in tokens:
            if not isinstance(record, dict) or record.get("token_hash") != token_hash:
                continue
            permissions = set(record.get("permissions") or [])
            if TokenPermission.WRITE.value in permissions:
                return TokenPermission.WRITE
            if TokenPermission.READ.value in permissions:
                return TokenPermission.READ
        return TokenPermission.INVALID

    def _refresh_projections(self, project_id: str) -> None:
        self.projections.render_projection(project_id, write=True)

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

    def _normalize_string_list(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    def _normalize_evidence_list(self, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return value
        raise ValueError("evidence must be a list")

    def _normalize_supporting_claims(self, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, str):
            return [{"claim_id": item} for item in self._normalize_string_list(value)]
        if isinstance(value, list):
            normalized: list[object] = []
            for item in value:
                if isinstance(item, str):
                    if item.strip():
                        normalized.append({"claim_id": item.strip()})
                else:
                    normalized.append(item)
            return normalized
        raise ValueError("supporting_claims must be a list")
