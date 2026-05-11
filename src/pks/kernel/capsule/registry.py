from __future__ import annotations

from pathlib import Path

from pks.kernel.capsule.id_generator import ClaimIdGenerator
from pks.kernel.capsule.policy import PolicyManager
from pks.kernel.capsule.projection_specs import ProjectionSpecManager
from pks.kernel.capsule.seeder import ProjectSeeder
from pks.kernel.capsule.taste import TasteManager
from pks.kernel.storage import read_yaml, write_yaml
from pks.models import (
    CapsuleDomain,
    CapsuleResolution,
    Claim,
    ClaimType,
    DomainPolicy,
    ProjectionSpec,
    ProjectMetadata,
)
from pks.paths import resolve_pks_home

PROJECT_RUNTIME_FIELDS = {
    "project_id",
    "name",
    "capsule_type",
    "domain",
    "external_project_path",
    "repository_url",
    "tracking",
}


class ProjectRegistry:
    def __init__(self, home: Path | None = None) -> None:
        self.home = resolve_pks_home(home)
        self.policy = PolicyManager(self.domains_dir)
        self.taste = TasteManager(self.domains_dir)
        self.specs = ProjectionSpecManager(self.capsules_dir)
        self.id_gen = ClaimIdGenerator(self.home)
        self.seeder = ProjectSeeder(self.capsules_dir, self.id_gen)

    @property
    def capsules_dir(self) -> Path:
        return self.home / "capsules"

    @property
    def domains_dir(self) -> Path:
        return self.home / "domains"

    def ensure_home(self) -> None:
        self.capsules_dir.mkdir(parents=True, exist_ok=True)
        self.policy.ensure_domain_dirs()
        self.id_gen.ensure_config()

    def capsule_path(self, project_id: str) -> Path:
        return self.capsules_dir / project_id

    def create_capsule(self, project: ProjectMetadata) -> Path:
        self.ensure_home()
        capsule_path = self.capsule_path(project.project_id)
        self.ensure_capsule_layout(project.project_id)
        self.save_project(project)
        self.seeder.seed_project_claims(project)
        return capsule_path

    def ensure_capsule_layout(self, project_id: str) -> None:
        self.seeder.ensure_capsule_layout(project_id)

    def save_project(self, project: ProjectMetadata) -> None:
        write_yaml(
            self.capsule_path(project.project_id) / "project.yaml",
            project.model_dump(
                mode="json",
                exclude_none=True,
                exclude={"stage", "current_goal", "deliverable", "constraints"},
            ),
        )

    def update_project(self, project_id: str, **updates: object) -> ProjectMetadata:
        disallowed = sorted(set(updates) - PROJECT_RUNTIME_FIELDS)
        if disallowed:
            raise ValueError(
                "project.yaml only stores runtime metadata; use Claim APIs for "
                + ", ".join(disallowed)
            )
        data = self.load_project(project_id).model_dump(mode="python")
        data.update({key: value for key, value in updates.items() if value is not None})
        updated = ProjectMetadata.model_validate(data)
        self.save_project(updated)
        return updated

    def load_project(self, project_id: str) -> ProjectMetadata:
        project_path = self.capsule_path(project_id) / "project.yaml"
        raw_data = read_yaml(project_path)
        project = ProjectMetadata.model_validate(raw_data)
        if self.seeder.migrate_capsule_if_needed(project, raw_data):
            self.save_project(project)
        return ProjectMetadata.model_validate(read_yaml(project_path))

    def resolve_project(self, project_id: str) -> CapsuleResolution:
        return CapsuleResolution(
            project=self.load_project(project_id),
            capsule_path=self.capsule_path(project_id),
        )

    def list_projects(self) -> list[ProjectMetadata]:
        if not self.capsules_dir.exists():
            return []
        return [
            ProjectMetadata.model_validate(read_yaml(project_yaml))
            for project_yaml in sorted(self.capsules_dir.glob("*/project.yaml"))
        ]

    def load_policy(self, domain: CapsuleDomain | str) -> DomainPolicy:
        return self.policy.load_policy(domain)

    def save_policy(self, policy: DomainPolicy) -> DomainPolicy:
        return self.policy.save_policy(policy)

    def validate_policy(self, domain: CapsuleDomain | str) -> list[str]:
        return self.policy.validate_policy(domain)

    def next_claim_id(self, claim_type: ClaimType | str) -> str:
        return self.id_gen.next_claim_id(claim_type)

    def save_taste_claim(self, claim: Claim, capsule_type: str | None = None) -> None:
        self.taste.save_taste_claim(claim, capsule_type)

    def list_taste_claims(
        self,
        domain: CapsuleDomain | str,
        capsule_type: str | None = None,
    ) -> list[Claim]:
        return self.taste.list_taste_claims(domain, capsule_type)

    def list_projection_specs(self, project_id: str, capsule_type: str) -> list[ProjectionSpec]:
        return self.specs.list_projection_specs(project_id, capsule_type)

    def list_custom_projection_specs(self, project_id: str) -> list[ProjectionSpec]:
        return self.specs.list_custom_projection_specs(project_id)

    def save_projection_spec(self, project_id: str, spec: ProjectionSpec) -> ProjectionSpec:
        return self.specs.save_projection_spec(project_id, spec)

    def load_custom_projection_spec(self, project_id: str, projection_id: str) -> ProjectionSpec:
        return self.specs.load_custom_projection_spec(project_id, projection_id)

    def delete_projection_spec(self, project_id: str, projection_id: str) -> None:
        self.specs.delete_projection_spec(project_id, projection_id)

    def projection_specs_dir(self, project_id: str) -> Path:
        return self.specs.projection_specs_dir(project_id)

    def projection_spec_path(self, project_id: str, projection_id: str) -> Path:
        return self.specs.projection_spec_path(project_id, projection_id)

    def load_projection_hashes(self, project_id: str) -> dict[str, str]:
        return self.specs.load_projection_hashes(project_id)

    def save_projection_hashes(self, project_id: str, hashes: dict[str, str]) -> None:
        self.specs.save_projection_hashes(project_id, hashes)

    def projection_hashes_path(self, project_id: str) -> Path:
        return self.specs.projection_hashes_path(project_id)
