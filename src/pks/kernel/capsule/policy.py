from __future__ import annotations

from pathlib import Path

from pks.kernel.storage import read_yaml, write_yaml
from pks.models import CapsuleDomain, ClaimType, DomainPolicy

DOMAIN_TYPE_SLUGS: dict[str, tuple[str, ...]] = {
    CapsuleDomain.DEV.value: ("software", "plugin"),
    CapsuleDomain.CONTENT.value: ("article", "video", "game"),
    CapsuleDomain.RESEARCH.value: ("discipline", "model"),
}


class PolicyManager:
    def __init__(self, domains_dir: Path) -> None:
        self.domains_dir = domains_dir

    def ensure_domain_dirs(self) -> None:
        self.domains_dir.mkdir(parents=True, exist_ok=True)
        for domain in CapsuleDomain:
            domain_dir = self.domains_dir / domain.value
            (domain_dir / "taste_and_style" / "claims").mkdir(parents=True, exist_ok=True)
            for type_slug in DOMAIN_TYPE_SLUGS[domain.value]:
                (domain_dir / "types" / type_slug / "taste_and_style" / "claims").mkdir(
                    parents=True,
                    exist_ok=True,
                )
            self._ensure_policy_file(domain)

    def load_policy(self, domain: CapsuleDomain | str) -> DomainPolicy:
        domain_value = domain.value if isinstance(domain, CapsuleDomain) else str(domain)
        policy_path = self.domains_dir / domain_value / "claim_policy.yaml"
        if not policy_path.exists():
            return DomainPolicy.default_for(domain_value)
        return DomainPolicy.model_validate(read_yaml(policy_path))

    def save_policy(self, policy: DomainPolicy) -> DomainPolicy:
        domain_value = policy.domain_value
        policy_path = self.domains_dir / domain_value / "claim_policy.yaml"
        write_yaml(policy_path, policy.model_dump(mode="json", exclude_none=True))
        return policy

    def validate_policy(self, domain: CapsuleDomain | str) -> list[str]:
        policy = self.load_policy(domain)
        issues: list[str] = []
        levels = {
            ClaimType.FACTUAL.value: 0,
            ClaimType.INFERENCE.value: 1,
            ClaimType.PREFERENCE.value: 2,
            ClaimType.CONSTRAINT.value: 3,
        }
        for claim_type in ClaimType:
            if claim_type.value not in policy.lifecycle:
                issues.append(f"missing lifecycle rule for {claim_type.value}")
            if claim_type.value not in policy.min_support:
                issues.append(f"missing min_support rule for {claim_type.value}")
        for claim_type, rule in policy.min_support.items():
            if claim_type not in levels:
                issues.append(f"unknown min_support claim type: {claim_type}")
                continue
            for support_type in rule.allowed_support_types:
                if support_type not in levels:
                    issues.append(f"{claim_type} allows unknown support type: {support_type}")
                elif levels[support_type] >= levels[claim_type]:
                    issues.append(f"{claim_type} cannot be supported by {support_type}")
        return issues

    def _ensure_policy_file(self, domain: CapsuleDomain) -> None:
        policy_path = self.domains_dir / domain.value / "claim_policy.yaml"
        if not policy_path.exists():
            policy = DomainPolicy.default_for(domain)
            write_yaml(policy_path, policy.model_dump(mode="json", exclude_none=True))
            return
        policy = DomainPolicy.model_validate(read_yaml(policy_path))
        default_policy = DomainPolicy.default_for(domain)
        changed = self._fill_missing_policy_defaults(policy, default_policy)
        if changed:
            write_yaml(policy_path, policy.model_dump(mode="json", exclude_none=True))

    def _fill_missing_policy_defaults(
        self,
        policy: DomainPolicy,
        default_policy: DomainPolicy,
    ) -> bool:
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
        return changed
