from __future__ import annotations

from pathlib import Path

from pks.kernel.capsule.layout import domain_modules, render_project_doc
from pks.kernel.storage import read_yaml, write_yaml
from pks.models import CapsuleDomain, Claim, DomainPolicy, ProjectMetadata
from pks.paths import resolve_pks_home


class ProjectRegistry:
    def __init__(self, home: Path | None = None) -> None:
        self.home = resolve_pks_home(home)

    @property
    def capsules_dir(self) -> Path:
        return self.home / "capsules"

    @property
    def domains_dir(self) -> Path:
        return self.home / "domains"

    def ensure_home(self) -> None:
        self.capsules_dir.mkdir(parents=True, exist_ok=True)
        self.domains_dir.mkdir(parents=True, exist_ok=True)

        for domain in CapsuleDomain:
            domain_dir = self.domains_dir / domain.value
            (domain_dir / "taste_and_style" / "claims").mkdir(parents=True, exist_ok=True)
            policy_path = domain_dir / "claim_policy.yaml"
            if not policy_path.exists():
                policy = DomainPolicy.default_for(domain)
                write_yaml(policy_path, policy.model_dump(mode="json", exclude_none=True))

        config_path = self.home / "config.yaml"
        if not config_path.exists():
            write_yaml(config_path, {"version": 1, "capsules_dir": "capsules"})

    def capsule_path(self, project_id: str) -> Path:
        return self.capsules_dir / project_id

    def create_capsule(self, project: ProjectMetadata) -> Path:
        self.ensure_home()
        capsule_path = self.capsule_path(project.project_id)
        capsule_path.mkdir(parents=True, exist_ok=True)
        (capsule_path / "claims").mkdir(exist_ok=True)

        for filename in domain_modules(project.domain):
            module_path = capsule_path / filename
            if not module_path.exists():
                title = filename.removesuffix(".md").replace("_", " ").title()
                module_path.write_text(f"# {title}\n\n", encoding="utf-8")

        self.save_project(project)

        project_doc = capsule_path / "PKS_PROJECT.md"
        if not project_doc.exists():
            project_doc.write_text(render_project_doc(project), encoding="utf-8")

        journal = capsule_path / "journal.md"
        if not journal.exists():
            journal.write_text("# Journal\n\n", encoding="utf-8")

        return capsule_path

    def save_project(self, project: ProjectMetadata) -> None:
        write_yaml(
            self.capsule_path(project.project_id) / "project.yaml",
            project.model_dump(mode="json", exclude_none=True),
        )

    def load_project(self, project_id: str) -> ProjectMetadata:
        data = read_yaml(self.capsule_path(project_id) / "project.yaml")
        return ProjectMetadata.model_validate(data)

    def list_projects(self) -> list[ProjectMetadata]:
        if not self.capsules_dir.exists():
            return []
        projects: list[ProjectMetadata] = []
        for project_yaml in sorted(self.capsules_dir.glob("*/project.yaml")):
            projects.append(ProjectMetadata.model_validate(read_yaml(project_yaml)))
        return projects

    def load_policy(self, domain: CapsuleDomain | str) -> DomainPolicy:
        domain_value = domain.value if isinstance(domain, CapsuleDomain) else str(domain)
        policy_path = self.domains_dir / domain_value / "claim_policy.yaml"
        if not policy_path.exists():
            return DomainPolicy.default_for(domain_value)
        return DomainPolicy.model_validate(read_yaml(policy_path))

    def taste_claims_dir(self, domain: CapsuleDomain | str) -> Path:
        domain_value = domain.value if isinstance(domain, CapsuleDomain) else str(domain)
        return self.domains_dir / domain_value / "taste_and_style" / "claims"

    def save_taste_claim(self, claim: Claim) -> None:
        self.ensure_home()
        claim_path = self.taste_claims_dir(claim.domain_value) / f"{claim.claim_id}.yaml"
        write_yaml(claim_path, claim.model_dump(mode="json", exclude_none=True))

    def list_taste_claims(self, domain: CapsuleDomain | str) -> list[Claim]:
        claims_dir = self.taste_claims_dir(domain)
        if not claims_dir.exists():
            return []
        return [
            Claim.model_validate(read_yaml(path))
            for path in sorted(claims_dir.glob("*.yaml"))
        ]
