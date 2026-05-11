from __future__ import annotations

from pathlib import Path

from pks.kernel.storage import read_yaml, write_yaml
from pks.models import CapsuleDomain, Claim

CAPSULE_TYPE_SLUGS: dict[str, str] = {
    "SoftwareCapsule": "software",
    "PluginCapsule": "plugin",
    "ArticleCapsule": "article",
    "VideoCapsule": "video",
    "GameCapsule": "game",
    "DisciplineCapsule": "discipline",
    "ModelCapsule": "model",
}


class TasteManager:
    def __init__(self, domains_dir: Path) -> None:
        self.domains_dir = domains_dir

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

    def save_taste_claim(self, claim: Claim, capsule_type: str | None = None) -> None:
        claims_dir = (
            self.type_taste_claims_dir(claim.domain_value, capsule_type)
            if capsule_type
            else self.taste_claims_dir(claim.domain_value)
        )
        claims_dir.mkdir(parents=True, exist_ok=True)
        write_yaml(
            claims_dir / f"{claim.claim_id}.yaml",
            claim.model_dump(mode="json", exclude_none=True),
        )

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

    def _list_claims_in(self, claims_dir: Path) -> list[Claim]:
        if not claims_dir.exists():
            return []
        return [Claim.model_validate(read_yaml(path)) for path in sorted(claims_dir.glob("*.yaml"))]
