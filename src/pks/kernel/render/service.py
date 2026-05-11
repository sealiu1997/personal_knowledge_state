from __future__ import annotations

import hashlib
from pathlib import Path

from pks.kernel.capsule import ProjectRegistry
from pks.kernel.claim.workflow import ClaimWorkflow
from pks.kernel.health import HealthEngine
from pks.kernel.render.projection import ProjectionEngine, claim_matches_projection
from pks.models import (
    Claim,
    ClaimStatus,
    ProjectionIssue,
    ProjectionSpec,
    ProjectMetadata,
    ReviewDecision,
)


class ProjectionService:
    def __init__(
        self,
        registry: ProjectRegistry,
        engine: ProjectionEngine,
        health: HealthEngine,
        claims: ClaimWorkflow,
    ) -> None:
        self.registry = registry
        self.engine = engine
        self.health = health
        self.claims = claims

    def render_context(self, project_id: str) -> str:
        project = self.registry.load_project(project_id)
        claims = self._context_claims(project)
        return self.engine.render_markdown(
            project,
            claims,
            self.registry.capsule_path(project_id),
            self.list_projections(project_id),
            self.health.stale_claim_ids_for(project_id, claims),
        )

    def render_projection(
        self,
        project_id: str,
        projection_id: str | None = None,
        write: bool = False,
    ) -> str | Path:
        project = self.registry.load_project(project_id)
        claims = self._context_claims(project)
        capsule_path = self.registry.capsule_path(project_id)
        stale_ids = self.health.stale_claim_ids_for(project_id, claims)
        specs = self.list_projections(project_id)
        if projection_id:
            spec = self.projection_spec(project, projection_id)
            if not write:
                return self.engine.render_projection(spec, claims, stale_ids)
            path = self.engine.write_capsule_projection(capsule_path, spec, claims, stale_ids)
            self._record_projection_hash(project_id, spec, path)
            return path
        if not write:
            return self.engine.render_markdown(project, claims, capsule_path, specs, stale_ids)
        for spec in specs:
            path = self.engine.write_capsule_projection(capsule_path, spec, claims, stale_ids)
            self._record_projection_hash(project_id, spec, path)
        if project.project_root() is None:
            return self.engine.render_markdown(project, claims, capsule_path, specs, stale_ids)
        return self.engine.write_projection(project, claims, capsule_path, specs, stale_ids)

    def check_integrity(self, project_id: str) -> list[ProjectionIssue]:
        capsule_path = self.registry.capsule_path(project_id)
        hashes = self.registry.load_projection_hashes(project_id)
        issues: list[ProjectionIssue] = []
        for spec in self.list_projections(project_id):
            path = capsule_path / spec.output_path
            expected_hash = hashes.get(spec.output_path)
            if not path.exists():
                issues.append(self._projection_issue(spec, "projection file missing"))
            elif expected_hash is None:
                issues.append(self._projection_issue(spec, "projection hash missing"))
            elif self._file_hash(path) != expected_hash:
                issues.append(self._projection_issue(spec, "projection modified outside Kernel"))
        return issues

    def list_projections(self, project_id: str) -> list[ProjectionSpec]:
        project = self.registry.load_project(project_id)
        return self.registry.list_projection_specs(project_id, project.capsule_type)

    def load_projection_spec(self, project_id: str, projection_id: str) -> ProjectionSpec:
        return self.projection_spec(self.registry.load_project(project_id), projection_id)

    def create_projection_spec(self, project_id: str, spec: ProjectionSpec) -> ProjectionSpec:
        project = self.registry.load_project(project_id)
        saved = self.registry.save_projection_spec(project_id, spec)
        self.claims.audit_factory(project).record(
            project,
            "projection_spec.create",
            subject=f"projection {spec.projection_id}",
            predicate="was_created_by",
            object_="kernel",
            payload={"projection_id": spec.projection_id},
        )
        self.render_projection(project_id, write=True)
        return saved

    def update_projection_spec(
        self,
        project_id: str,
        projection_id: str,
        changes: dict[str, object],
    ) -> ProjectionSpec:
        project = self.registry.load_project(project_id)
        data = self.projection_spec(project, projection_id).model_dump(mode="python")
        data.update(changes)
        updated = ProjectionSpec.model_validate(data)
        saved = self.registry.save_projection_spec(project_id, updated)
        self.claims.audit_factory(project).record(
            project,
            "projection_spec.update",
            subject=f"projection {projection_id}",
            predicate="was_updated_by",
            object_="kernel",
            payload={"projection_id": projection_id, "fields": ",".join(sorted(changes))},
        )
        self.render_projection(project_id, write=True)
        return saved

    def delete_projection_spec(self, project_id: str, projection_id: str) -> None:
        project = self.registry.load_project(project_id)
        spec = self.projection_spec(project, projection_id)
        self.registry.delete_projection_spec(project_id, projection_id)
        (self.registry.capsule_path(project_id) / spec.output_path).unlink(missing_ok=True)
        hashes = self.registry.load_projection_hashes(project_id)
        hashes.pop(spec.output_path, None)
        self.registry.save_projection_hashes(project_id, hashes)
        self.claims.audit_factory(project).record(
            project,
            "projection_spec.delete",
            subject=f"projection {projection_id}",
            predicate="was_deleted_by",
            object_="kernel",
            payload={"projection_id": projection_id},
        )
        self.render_projection(project_id, write=True)

    def submit_projection_claim(
        self,
        project_id: str,
        projection_id: str,
        claim_draft: Claim,
    ) -> ReviewDecision:
        project = self.registry.load_project(project_id)
        spec = self.projection_spec(project, projection_id)
        claim_draft.tags = sorted(set(claim_draft.tags).union(spec.filters.tags))
        return self.claims.submit_candidate(project_id, claim_draft)

    def patch_projection_claim(
        self,
        project_id: str,
        projection_id: str,
        claim_id: str,
        changes: dict[str, object],
    ) -> Claim | ReviewDecision:
        project = self.registry.load_project(project_id)
        spec = self.projection_spec(project, projection_id)
        claim = self.claims.load_claim(project_id, claim_id)
        stale_ids = self.health.stale_claim_ids_for(project_id, self._context_claims(project))
        if not claim_matches_projection(claim, spec, stale_ids):
            raise ValueError(f"claim {claim_id} does not belong to projection {projection_id}")
        if "type" in changes:
            raise ValueError("claim type is immutable")
        if {"subject", "predicate", "object"}.intersection(changes):
            data = claim.model_dump(mode="python")
            data.update(changes)
            data["claim_id"] = self.registry.next_claim_id(claim.type_value)
            data["supersedes"] = claim.claim_id
            data["status"] = ClaimStatus.CANDIDATE.value
            return self.claims.submit_candidate(project_id, Claim.model_validate(data))
        data = claim.model_dump(mode="python")
        data.update(changes)
        updated = Claim.model_validate(data)
        self.claims.claim_engine(project_id).require_min_support(updated)
        self.claims.claim_engine(project_id).save_claim(updated)
        self.claims.audit_factory(project).record(
            project,
            "projection.patch",
            subject=f"claim {claim_id}",
            predicate="was_patched_through",
            object_=projection_id,
            payload={"claim_id": claim_id, "projection_id": projection_id},
        )
        self.render_projection(project_id, projection_id, write=True)
        return updated

    def projection_spec(self, project: ProjectMetadata, projection_id: str) -> ProjectionSpec:
        for spec in self.registry.list_projection_specs(project.project_id, project.capsule_type):
            if spec.projection_id == projection_id:
                return spec
        raise KeyError(f"unknown projection: {projection_id}")

    def _context_claims(self, project: ProjectMetadata) -> list[Claim]:
        return self.claims.list_claims(project.project_id) + self.registry.list_taste_claims(
            project.domain,
            project.capsule_type,
        )

    def _projection_issue(self, spec: ProjectionSpec, reason: str) -> ProjectionIssue:
        return ProjectionIssue(
            projection_id=spec.projection_id,
            output_path=spec.output_path,
            reason=reason,
        )

    def _record_projection_hash(self, project_id: str, spec: ProjectionSpec, path: Path) -> None:
        hashes = self.registry.load_projection_hashes(project_id)
        hashes[spec.output_path] = self._file_hash(path)
        self.registry.save_projection_hashes(project_id, hashes)

    def _file_hash(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
