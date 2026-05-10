from __future__ import annotations

from pks.models import CapsuleDomain, ProjectionFilters, ProjectionSpec, ProjectMetadata

CAPSULE_TYPE_PROJECTIONS: dict[str, tuple[str, ...]] = {
    "SoftwareCapsule": ("project-summary", "journal", "dev-architecture", "dev-tasks"),
    "PluginCapsule": ("project-summary", "journal", "dev-architecture"),
    "ArticleCapsule": ("project-summary", "journal", "content-outline", "content-facts"),
    "VideoCapsule": ("project-summary", "journal", "content-outline"),
    "DisciplineCapsule": (
        "project-summary",
        "journal",
        "research-terminology",
        "research-hypotheses",
    ),
    "ModelCapsule": ("project-summary", "journal", "research-hypotheses"),
}

PROJECTION_SPECS: dict[str, ProjectionSpec] = {
    "project-summary": ProjectionSpec(
        projection_id="project-summary",
        output_path="projections/PKS_PROJECT.md",
        title="Project Summary",
        description="Project definition, boundaries, current stage, and goals.",
        include_status=["accepted"],
        exclude_stale=True,
        filters=ProjectionFilters(
            tags=["project", "boundary", "stage", "goal", "deliverable", "constraint"],
            predicates=[
                "current_stage",
                "current_goal",
                "expected_deliverable",
                "project_boundary",
            ],
        ),
        order=["type", "created_at"],
    ),
    "journal": ProjectionSpec(
        projection_id="journal",
        output_path="projections/journal.md",
        title="Project Journal",
        description="Timeline of decisions, experience, progress, and milestones.",
        include_status=["accepted"],
        exclude_stale=False,
        filters=ProjectionFilters(
            types=["inference", "preference", "constraint"],
            tags=["decision", "experience", "progress", "milestone"],
            exclude_tags=["audit"],
        ),
        order=["created_at"],
    ),
    "dev-architecture": ProjectionSpec(
        projection_id="dev-architecture",
        output_path="projections/architecture.md",
        title="Architecture & Decisions",
        include_status=["accepted"],
        exclude_stale=True,
        filters=ProjectionFilters(
            types=["factual", "inference", "constraint"],
            tags=["architecture", "design-decision", "tech-stack", "boundary"],
        ),
        order=["type", "created_at"],
    ),
    "dev-tasks": ProjectionSpec(
        projection_id="dev-tasks",
        output_path="projections/tasks.md",
        title="Tasks & Progress",
        include_status=["accepted"],
        exclude_stale=True,
        filters=ProjectionFilters(tags=["task", "todo", "in-progress", "done"]),
        order=["created_at"],
    ),
    "content-outline": ProjectionSpec(
        projection_id="content-outline",
        output_path="projections/outline.md",
        title="Outline",
        include_status=["accepted"],
        exclude_stale=True,
        filters=ProjectionFilters(tags=["outline", "section", "structure"]),
        order=["created_at"],
    ),
    "content-facts": ProjectionSpec(
        projection_id="content-facts",
        output_path="projections/facts.md",
        title="Facts",
        include_status=["accepted"],
        exclude_stale=True,
        filters=ProjectionFilters(types=["factual"], tags=["fact", "source"]),
        order=["created_at"],
    ),
    "research-terminology": ProjectionSpec(
        projection_id="research-terminology",
        output_path="projections/terminology.md",
        title="Terminology",
        include_status=["accepted"],
        exclude_stale=True,
        filters=ProjectionFilters(tags=["term", "definition", "terminology"]),
        order=["created_at"],
    ),
    "research-hypotheses": ProjectionSpec(
        projection_id="research-hypotheses",
        output_path="projections/hypotheses.md",
        title="Hypotheses",
        include_status=["accepted"],
        exclude_stale=True,
        filters=ProjectionFilters(types=["inference"], tags=["hypothesis"]),
        order=["created_at"],
    ),
}


def domain_modules(domain: CapsuleDomain | str) -> tuple[str, ...]:
    domain_value = domain.value if isinstance(domain, CapsuleDomain) else str(domain)
    modules_by_domain: dict[str, tuple[str, ...]] = {
        CapsuleDomain.CONTENT.value: ("outline.md", "facts.md"),
        CapsuleDomain.DEV.value: ("architecture.md", "tasks.md"),
        CapsuleDomain.RESEARCH.value: ("terminology.md", "hypotheses.md"),
    }
    return modules_by_domain.get(domain_value, ())


def default_projection_specs(capsule_type: str) -> list[ProjectionSpec]:
    projection_ids = CAPSULE_TYPE_PROJECTIONS.get(capsule_type, ("project-summary", "journal"))
    return [PROJECTION_SPECS[projection_id] for projection_id in projection_ids]


def projection_spec(capsule_type: str, projection_id: str) -> ProjectionSpec:
    specs = {spec.projection_id: spec for spec in default_projection_specs(capsule_type)}
    if projection_id not in specs:
        raise KeyError(f"unknown projection for {capsule_type}: {projection_id}")
    return specs[projection_id]


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
