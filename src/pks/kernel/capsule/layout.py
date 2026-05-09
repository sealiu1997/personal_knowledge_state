from __future__ import annotations

from pks.models import CapsuleDomain, ProjectMetadata

DOMAIN_MODULES: dict[str, tuple[str, ...]] = {
    CapsuleDomain.CONTENT.value: ("outline.md", "facts.md"),
    CapsuleDomain.DEV.value: ("architecture.md", "tasks.md"),
    CapsuleDomain.RESEARCH.value: ("terminology.md", "hypotheses.md"),
}


def domain_modules(domain: CapsuleDomain | str) -> tuple[str, ...]:
    domain_value = domain.value if isinstance(domain, CapsuleDomain) else str(domain)
    return DOMAIN_MODULES.get(domain_value, ())


def render_project_doc(project: ProjectMetadata) -> str:
    lines = [
        f"# {project.name}",
        "",
        "## Definition",
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
        lines.append(f"- Project path: `{project.project_root()}`")
    if project.repository_url:
        lines.append(f"- Repository: {project.repository_url}")

    lines.extend(["", "## Boundaries", ""])
    if project.constraints:
        lines.extend([f"- {constraint}" for constraint in project.constraints])
    else:
        lines.append("- Context Packs are generated dynamically and are not stored here.")

    lines.extend(
        [
            "- PKS state lives outside the project folder.",
            "- Agents submit candidate Claims with evidence.",
            "- Agents do not mutate accepted state.",
            "",
        ]
    )
    return "\n".join(lines)
