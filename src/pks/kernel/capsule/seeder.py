from __future__ import annotations

from datetime import date
from pathlib import Path

from pks.kernel.capsule.id_generator import ClaimIdGenerator
from pks.kernel.claim.store import ClaimStore
from pks.models import (
    Claim,
    ClaimType,
    Evidence,
    ProjectMetadata,
    Relation,
    SupportingClaim,
)


class ProjectSeeder:
    def __init__(self, capsules_dir: Path, id_generator: ClaimIdGenerator) -> None:
        self.capsules_dir = capsules_dir
        self.id_generator = id_generator

    def seed_project_claims(self, project: ProjectMetadata) -> None:
        self.ensure_capsule_layout(project.project_id)
        store = ClaimStore(self.capsule_path(project.project_id))
        for claim in self._initial_claims(project):
            if not self._has_project_claim(store, claim.predicate, claim.object):
                store.save(claim)

    def migrate_capsule_if_needed(
        self,
        project: ProjectMetadata,
        raw_data: dict[str, object],
    ) -> bool:
        self.ensure_capsule_layout(project.project_id)
        if not {"stage", "current_goal", "deliverable", "constraints"}.intersection(raw_data):
            return False
        self.seed_project_claims(project)
        return True

    def ensure_capsule_layout(self, project_id: str) -> None:
        capsule_path = self.capsule_path(project_id)
        capsule_path.mkdir(parents=True, exist_ok=True)
        for dirname in ("claims", "candidates", "projections", "projection_specs"):
            (capsule_path / dirname).mkdir(exist_ok=True)

    def capsule_path(self, project_id: str) -> Path:
        return self.capsules_dir / project_id

    def _initial_claims(self, project: ProjectMetadata) -> list[Claim]:
        today = date.today()
        evidence = Evidence(
            source_ref="manual",
            source_type="manual",
            relation=Relation.SUPPORTS,
            excerpt="Initial capsule metadata provided by the user.",
        )
        seeds = [
            self._seed_claim(project, ClaimType.FACTUAL, predicate, object_, [tag], evidence, today)
            for predicate, object_, tag in (
                ("current_stage", project.stage, "stage"),
                ("current_goal", project.current_goal, "goal"),
                ("expected_deliverable", project.deliverable, "deliverable"),
            )
            if object_
        ]
        support = self._constraint_support(project, evidence, today)
        if support:
            seeds.append(support)
        seeds.extend(
            self._constraint_claim(project, item, evidence, today, support)
            for item in project.constraints
        )
        return seeds

    def _constraint_support(
        self,
        project: ProjectMetadata,
        evidence: Evidence,
        today: date,
    ) -> Claim | None:
        if not project.constraints:
            return None
        return self._seed_claim(
            project,
            ClaimType.FACTUAL,
            "initial_constraints_source",
            "user provided explicit capsule constraints",
            ["constraint-source"],
            evidence,
            today,
        )

    def _constraint_claim(
        self,
        project: ProjectMetadata,
        constraint: str,
        evidence: Evidence,
        today: date,
        support: Claim | None,
    ) -> Claim:
        supporting_claims = [SupportingClaim(claim_id=support.claim_id)] if support else []
        return self._seed_claim(
            project,
            ClaimType.CONSTRAINT,
            "project_boundary",
            constraint,
            ["boundary", "constraint"],
            evidence,
            today,
            supporting_claims,
        )

    def _seed_claim(
        self,
        project: ProjectMetadata,
        claim_type: ClaimType,
        predicate: str,
        object_: str,
        tags: list[str],
        evidence: Evidence,
        today: date,
        supporting_claims: list[SupportingClaim] | None = None,
    ) -> Claim:
        return Claim(
            claim_id=self.id_generator.next_claim_id(claim_type),
            subject=project.project_id,
            predicate=predicate,
            object=object_,
            content=object_,
            type=claim_type,
            domain=project.domain,
            tags=["project", *tags],
            evidence=[evidence],
            supporting_claims=supporting_claims or [],
            status="accepted",
            confidence=1.0,
            created_by="human",
            last_verified=today,
            project=project.project_id,
        )

    def _has_project_claim(self, store: ClaimStore, predicate: str, object_: str) -> bool:
        return any(
            claim.predicate == predicate and claim.object == object_
            for claim in store.list()
        )
