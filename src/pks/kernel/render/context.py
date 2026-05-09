from __future__ import annotations

from pathlib import Path

from pks.models import Claim, ProjectMetadata


class ContextEngine:
    def render_markdown(
        self,
        project: ProjectMetadata,
        claims: list[Claim],
        capsule_path: Path | None = None,
        stale_claim_ids: set[str] | None = None,
    ) -> str:
        stale_claim_ids = stale_claim_ids or set()
        accepted_claims = [
            claim
            for claim in claims
            if claim.is_context_eligible(stale=claim.claim_id in stale_claim_ids)
        ]
        lines = [
            f"# {project.name} Context Pack",
            "",
            "## Project",
            "",
            f"- Project ID: `{project.project_id}`",
            f"- Capsule type: `{project.capsule_type}`",
            f"- Domain: `{project.domain_value}`",
            f"- Stage: {project.stage}",
        ]

        if project.current_goal:
            lines.append(f"- Current goal: {project.current_goal}")
        if project.deliverable:
            lines.append(f"- Deliverable: {project.deliverable}")
        if project.project_root():
            lines.append(f"- External project path: `{project.project_root()}`")
        if project.repository_url:
            lines.append(f"- Repository: {project.repository_url}")

        if project.constraints:
            lines.extend(["", "## Constraints", ""])
            lines.extend([f"- {constraint}" for constraint in project.constraints])

        lines.extend(["", "## Accepted Claims", ""])
        if accepted_claims:
            for claim in accepted_claims:
                lines.append(f"- `{claim.claim_id}`: {claim.display_content()}")
        else:
            lines.append("- No accepted claims available for context.")

        lines.extend(
            [
                "",
                "## Boundaries",
                "",
                "- PKS state is authoritative; this Context Pack is a generated projection.",
                "- Agents may submit candidates, but must not directly mutate accepted state.",
            ]
        )

        if capsule_path:
            lines.extend(["", "## PKS Capsule", "", f"- Capsule path: `{capsule_path}`"])

        lines.extend(
            [
                "",
                "## Agent Interface",
                "",
                "- Prefer MCP or CLI calls for additional project context.",
                "- Submit new long-term knowledge as candidate Claims with evidence.",
                "",
            ]
        )
        return "\n".join(lines)
