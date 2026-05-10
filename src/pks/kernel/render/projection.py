from __future__ import annotations

from pathlib import Path

from pks.models import Claim, ProjectionSpec, ProjectMetadata

GENERATED_HEADER = "<!-- Generated from Claims. Do not edit directly. -->"


def claim_matches_projection(
    claim: Claim,
    spec: ProjectionSpec,
    stale_claim_ids: set[str] | None = None,
) -> bool:
    stale_claim_ids = stale_claim_ids or set()
    if claim.status_value not in spec.include_status:
        return False
    if spec.exclude_stale and claim.claim_id in stale_claim_ids:
        return False
    if spec.filters.domains and claim.domain_value not in spec.filters.domains:
        return False
    if spec.filters.types and claim.type_value not in spec.filters.types:
        return False
    if spec.filters.exclude_tags and set(spec.filters.exclude_tags).intersection(claim.tags):
        return False
    tag_match = bool(set(spec.filters.tags).intersection(claim.tags))
    predicate_match = claim.predicate in spec.filters.predicates
    if spec.filters.tags and spec.filters.predicates:
        return tag_match or predicate_match
    if spec.filters.tags and not tag_match:
        return False
    if spec.filters.predicates and not predicate_match:
        return False
    return True


class ProjectionEngine:
    def render_markdown(
        self,
        project: ProjectMetadata,
        claims: list[Claim],
        capsule_path: Path,
        specs: list[ProjectionSpec] | None = None,
        stale_claim_ids: set[str] | None = None,
    ) -> str:
        if specs:
            return self.render_context(project, claims, capsule_path, specs, stale_claim_ids)
        stale_claim_ids = stale_claim_ids or set()
        accepted_claims = [
            claim
            for claim in claims
            if claim.is_context_eligible(stale=claim.claim_id in stale_claim_ids)
        ]
        lines = [
            GENERATED_HEADER,
            "",
            f"# PKS Projection: {project.name}",
            "",
            "This file is generated from Claims. It is not a source of truth.",
            "",
            "## Project",
            "",
            f"- Project ID: `{project.project_id}`",
            f"- PKS capsule: `{capsule_path}`",
        ]

        lines.extend(["", "## Accepted Claims", ""])
        if accepted_claims:
            lines.extend(
                [f"- `{claim.claim_id}`: {claim.display_content()}" for claim in accepted_claims]
            )
        else:
            lines.append("- No accepted claims available for projection.")

        lines.extend(
            [
                "",
                "## Agent Note",
                "",
                "- Use PKS CLI or MCP for deeper context.",
                "- Submit durable knowledge as candidate Claims with evidence.",
                "",
            ]
        )
        return "\n".join(lines)

    def render_projection(
        self,
        spec: ProjectionSpec,
        claims: list[Claim],
        stale_claim_ids: set[str] | None = None,
    ) -> str:
        matched_claims = [
            claim
            for claim in claims
            if claim_matches_projection(claim, spec, stale_claim_ids)
        ]
        matched_claims = self._sort_claims(matched_claims, spec.order)
        lines = [
            GENERATED_HEADER,
            "",
            f"# {spec.title}",
            "",
        ]
        if spec.description:
            lines.extend([spec.description, ""])
        if matched_claims:
            lines.extend(
                f"- `{claim.claim_id}` [{claim.type_value}] {claim.display_content()}"
                for claim in matched_claims
            )
        else:
            lines.append("- No matching claims.")
        lines.append("")
        return "\n".join(lines)

    def render_context(
        self,
        project: ProjectMetadata,
        claims: list[Claim],
        capsule_path: Path,
        specs: list[ProjectionSpec],
        stale_claim_ids: set[str] | None = None,
    ) -> str:
        lines = [
            GENERATED_HEADER,
            "",
            f"# {project.name} PKS.md",
            "",
            "PKS.md is the materialized Content Pack generated from accepted Claims.",
            "",
            f"- Project ID: `{project.project_id}`",
            f"- Capsule type: `{project.capsule_type}`",
            f"- Domain: `{project.domain_value}`",
            f"- PKS capsule: `{capsule_path}`",
            "",
        ]
        for spec in specs:
            rendered = self.render_projection(spec, claims, stale_claim_ids)
            body = rendered.split("\n", 2)[2].strip()
            lines.extend([body, ""])
        taste_claims = [
            claim
            for claim in claims
            if claim.project.startswith("domain:")
            and claim.is_context_eligible(stale=claim.claim_id in (stale_claim_ids or set()))
        ]
        if taste_claims:
            lines.extend(["# Taste & Style", ""])
            for claim in self._sort_claims(taste_claims, ["created_at"]):
                lines.append(f"- `{claim.claim_id}` [{claim.type_value}] {claim.display_content()}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def write_capsule_projection(
        self,
        capsule_path: Path,
        spec: ProjectionSpec,
        claims: list[Claim],
        stale_claim_ids: set[str] | None = None,
    ) -> Path:
        output_path = capsule_path / spec.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self.render_projection(spec, claims, stale_claim_ids),
            encoding="utf-8",
        )
        return output_path

    def write_projection(
        self,
        project: ProjectMetadata,
        claims: list[Claim],
        capsule_path: Path,
        specs: list[ProjectionSpec] | None = None,
        stale_claim_ids: set[str] | None = None,
    ) -> Path:
        project_root = project.project_root()
        if project_root is None:
            raise ValueError("project path is required to write PKS.md projection")
        output_path = project_root.expanduser() / "PKS.md"
        output_path.write_text(
            self.render_markdown(project, claims, capsule_path, specs, stale_claim_ids),
            encoding="utf-8",
        )
        return output_path

    def _sort_claims(self, claims: list[Claim], order: list[str]) -> list[Claim]:
        sorted_claims = claims
        for key in reversed(order):
            if key == "type":
                sorted_claims = sorted(sorted_claims, key=lambda claim: claim.type_value)
            elif key == "created_at":
                sorted_claims = sorted(sorted_claims, key=lambda claim: claim.created_at)
            elif key == "predicate":
                sorted_claims = sorted(sorted_claims, key=lambda claim: claim.predicate)
        return sorted_claims
