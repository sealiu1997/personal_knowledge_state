from __future__ import annotations

from datetime import date
from pathlib import Path

from pks.kernel.capsule.layout import default_projection_specs
from pks.kernel.claim.store import ClaimStore
from pks.kernel.storage import read_yaml, write_yaml
from pks.models import (
    CapsuleDomain,
    CapsuleResolution,
    Claim,
    ClaimStatus,
    ClaimType,
    DomainPolicy,
    Evidence,
    ProjectMetadata,
    Relation,
    SupportingClaim,
)
from pks.paths import resolve_pks_home

TYPE_CODE: dict[str, str] = {
    ClaimType.FACTUAL.value: "F",
    ClaimType.INFERENCE.value: "I",
    ClaimType.PREFERENCE.value: "P",
    ClaimType.CONSTRAINT.value: "C",
}

DOMAIN_TYPE_SLUGS: dict[str, tuple[str, ...]] = {
    CapsuleDomain.DEV.value: ("software", "plugin"),
    CapsuleDomain.CONTENT.value: ("article", "video", "game"),
    CapsuleDomain.RESEARCH.value: ("discipline", "model"),
}

CAPSULE_TYPE_SLUGS: dict[str, str] = {
    "SoftwareCapsule": "software",
    "PluginCapsule": "plugin",
    "ArticleCapsule": "article",
    "VideoCapsule": "video",
    "GameCapsule": "game",
    "DisciplineCapsule": "discipline",
    "ModelCapsule": "model",
}

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
            for type_slug in DOMAIN_TYPE_SLUGS[domain.value]:
                (domain_dir / "types" / type_slug / "taste_and_style" / "claims").mkdir(
                    parents=True,
                    exist_ok=True,
                )
            policy_path = domain_dir / "claim_policy.yaml"
            if not policy_path.exists():
                policy = DomainPolicy.default_for(domain)
                write_yaml(policy_path, policy.model_dump(mode="json", exclude_none=True))
            else:
                policy = DomainPolicy.model_validate(read_yaml(policy_path))
                default_policy = DomainPolicy.default_for(domain)
                changed = False
                for claim_type, rule in default_policy.lifecycle.items():
                    if claim_type not in policy.lifecycle:
                        policy.lifecycle[claim_type] = rule
                        changed = True
                for claim_type, rule in default_policy.min_support.items():
                    if claim_type not in policy.min_support:
                        policy.min_support[claim_type] = rule
                        changed = True
                if not policy.manual_review_types:
                    policy.manual_review_types = default_policy.manual_review_types
                    changed = True
                if changed:
                    write_yaml(policy_path, policy.model_dump(mode="json", exclude_none=True))

        config_path = self.home / "config.yaml"
        if not config_path.exists():
            write_yaml(config_path, {"version": 1, "capsules_dir": "capsules", "claim_sequence": 0})

    def capsule_path(self, project_id: str) -> Path:
        return self.capsules_dir / project_id

    def create_capsule(self, project: ProjectMetadata) -> Path:
        self.ensure_home()
        capsule_path = self.capsule_path(project.project_id)
        capsule_path.mkdir(parents=True, exist_ok=True)
        (capsule_path / "claims").mkdir(exist_ok=True)
        (capsule_path / "candidates").mkdir(exist_ok=True)
        (capsule_path / "projections").mkdir(exist_ok=True)
        (capsule_path / "projection_specs").mkdir(exist_ok=True)

        self.save_project(project)
        self._seed_project_claims(project)
        return capsule_path

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
        current = self.load_project(project_id)
        data = current.model_dump(mode="python")
        for key, value in updates.items():
            if value is not None:
                data[key] = value
        updated = ProjectMetadata.model_validate(data)
        self.save_project(updated)
        return updated

    def load_project(self, project_id: str) -> ProjectMetadata:
        data = read_yaml(self.capsule_path(project_id) / "project.yaml")
        return ProjectMetadata.model_validate(data)

    def resolve_project(self, project_id: str) -> CapsuleResolution:
        return CapsuleResolution(
            project=self.load_project(project_id),
            capsule_path=self.capsule_path(project_id),
        )

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

    def validate_policy(self, domain: CapsuleDomain | str) -> list[str]:
        policy = self.load_policy(domain)
        issues: list[str] = []
        for claim_type in ClaimType:
            if claim_type.value not in policy.lifecycle:
                issues.append(f"missing lifecycle rule for {claim_type.value}")
            if claim_type.value not in policy.min_support:
                issues.append(f"missing min_support rule for {claim_type.value}")

        type_levels = {
            ClaimType.FACTUAL.value: 0,
            ClaimType.INFERENCE.value: 1,
            ClaimType.PREFERENCE.value: 2,
            ClaimType.CONSTRAINT.value: 3,
        }
        for claim_type, rule in policy.min_support.items():
            if claim_type not in type_levels:
                issues.append(f"unknown min_support claim type: {claim_type}")
                continue
            for support_type in rule.allowed_support_types:
                if support_type not in type_levels:
                    issues.append(f"{claim_type} allows unknown support type: {support_type}")
                elif type_levels[support_type] >= type_levels[claim_type]:
                    issues.append(f"{claim_type} cannot be supported by {support_type}")
        return issues

    def taste_claims_dir(self, domain: CapsuleDomain | str) -> Path:
        domain_value = domain.value if isinstance(domain, CapsuleDomain) else str(domain)
        return self.domains_dir / domain_value / "taste_and_style" / "claims"

    def type_taste_claims_dir(self, domain: CapsuleDomain | str, capsule_type: str) -> Path:
        domain_value = domain.value if isinstance(domain, CapsuleDomain) else str(domain)
        type_slug = CAPSULE_TYPE_SLUGS.get(
            capsule_type,
            capsule_type.removesuffix("Capsule").lower(),
        )
        return self.domains_dir / domain_value / "types" / type_slug / "taste_and_style" / "claims"

    def save_taste_claim(self, claim: Claim) -> None:
        self.ensure_home()
        claim_path = self.taste_claims_dir(claim.domain_value) / f"{claim.claim_id}.yaml"
        write_yaml(claim_path, claim.model_dump(mode="json", exclude_none=True))

    def list_taste_claims(
        self,
        domain: CapsuleDomain | str,
        capsule_type: str | None = None,
    ) -> list[Claim]:
        claim_map: dict[tuple[str, str], Claim] = {}
        for claim in self._list_claims_in(self.taste_claims_dir(domain)):
            claim_map[claim.conflict_key] = claim
        if capsule_type:
            for claim in self._list_claims_in(self.type_taste_claims_dir(domain, capsule_type)):
                claim_map[claim.conflict_key] = claim
        return list(claim_map.values())

    def list_projection_specs(self, capsule_type: str) -> list:
        return default_projection_specs(capsule_type)

    def next_claim_id(self, claim_type: ClaimType | str) -> str:
        self.ensure_home()
        claim_type_value = (
            claim_type.value if isinstance(claim_type, ClaimType) else str(claim_type)
        )
        config_path = self.home / "config.yaml"
        config = read_yaml(config_path)
        sequence = int(config.get("claim_sequence", 0)) + 1
        config["claim_sequence"] = sequence
        write_yaml(config_path, config)
        return f"{TYPE_CODE[claim_type_value]}-{sequence:05d}"

    def _list_claims_in(self, claims_dir: Path) -> list[Claim]:
        if not claims_dir.exists():
            return []
        return [
            Claim.model_validate(read_yaml(path))
            for path in sorted(claims_dir.glob("*.yaml"))
        ]

    def _seed_project_claims(self, project: ProjectMetadata) -> None:
        store = ClaimStore(self.capsule_path(project.project_id))
        today = date.today()
        evidence = Evidence(
            source_ref="manual",
            source_type="manual",
            relation=Relation.SUPPORTS,
            excerpt="Initial capsule metadata provided by the user.",
        )

        seed_claims: list[Claim] = []
        if project.stage:
            seed_claims.append(
                self._project_seed_claim(
                    project,
                    ClaimType.FACTUAL,
                    "current_stage",
                    project.stage,
                    "stage",
                    evidence,
                    today,
                )
            )
        if project.current_goal:
            seed_claims.append(
                self._project_seed_claim(
                    project,
                    ClaimType.FACTUAL,
                    "current_goal",
                    project.current_goal,
                    "goal",
                    evidence,
                    today,
                )
            )
        if project.deliverable:
            seed_claims.append(
                self._project_seed_claim(
                    project,
                    ClaimType.FACTUAL,
                    "expected_deliverable",
                    project.deliverable,
                    "deliverable",
                    evidence,
                    today,
                )
            )

        constraint_support: Claim | None = None
        if project.constraints:
            constraint_support = self._project_seed_claim(
                project,
                ClaimType.FACTUAL,
                "initial_constraints_source",
                "user provided explicit capsule constraints",
                "constraint-source",
                evidence,
                today,
            )
            seed_claims.append(constraint_support)

        for constraint in project.constraints:
            seed_claims.append(
                Claim(
                    claim_id=self.next_claim_id(ClaimType.CONSTRAINT),
                    subject=project.project_id,
                    predicate="project_boundary",
                    object=constraint,
                    content=constraint,
                    type=ClaimType.CONSTRAINT,
                    domain=project.domain,
                    tags=["project", "boundary", "constraint"],
                    evidence=[evidence],
                    supporting_claims=[
                        SupportingClaim(claim_id=constraint_support.claim_id)
                    ]
                    if constraint_support
                    else [],
                    status=ClaimStatus.ACCEPTED,
                    confidence=1.0,
                    created_by="human",
                    last_verified=today,
                    project=project.project_id,
                )
            )

        for claim in seed_claims:
            store.save(claim)

    def _project_seed_claim(
        self,
        project: ProjectMetadata,
        claim_type: ClaimType,
        predicate: str,
        object_: str,
        tag: str,
        evidence: Evidence,
        today: date,
    ) -> Claim:
        return Claim(
            claim_id=self.next_claim_id(claim_type),
            subject=project.project_id,
            predicate=predicate,
            object=object_,
            content=object_,
            type=claim_type,
            domain=project.domain,
            tags=["project", tag],
            evidence=[evidence],
            status=ClaimStatus.ACCEPTED,
            confidence=1.0,
            created_by="human",
            last_verified=today,
            project=project.project_id,
        )
