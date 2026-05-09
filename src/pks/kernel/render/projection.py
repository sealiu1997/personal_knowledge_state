from __future__ import annotations

from pathlib import Path

from pks.models import Claim, ProjectMetadata


class ProjectionEngine:
    def render_markdown(
        self,
        project: ProjectMetadata,
        claims: list[Claim],
        capsule_path: Path,
        stale_claim_ids: set[str] | None = None,
    ) -> str:
        stale_claim_ids = stale_claim_ids or set()
        accepted_claims = [
            claim
            for claim in claims
            if claim.is_context_eligible(stale=claim.claim_id in stale_claim_ids)
        ]
        lines = [
            f"# PKS Projection: {project.name}",
            "",
            "This file is generated from PKS Kernel state. It is not a source of truth.",
            "",
            "## Project",
            "",
            f"- Project ID: `{project.project_id}`",
            f"- Stage: {project.stage}",
            f"- PKS capsule: `{capsule_path}`",
        ]
        if project.current_goal:
            lines.append(f"- Current goal: {project.current_goal}")

        if project.constraints:
            lines.extend(["", "## Boundaries", ""])
            lines.extend([f"- {constraint}" for constraint in project.constraints])

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

    def write_projection(
        self,
        project: ProjectMetadata,
        claims: list[Claim],
        capsule_path: Path,
        stale_claim_ids: set[str] | None = None,
    ) -> Path:
        project_root = project.project_root()
        if project_root is None:
            raise ValueError("project path is required to write PKS.md projection")
        output_path = project_root.expanduser() / "PKS.md"
        output_path.write_text(
            self.render_markdown(project, claims, capsule_path, stale_claim_ids),
            encoding="utf-8",
        )
        return output_path
