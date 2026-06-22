from __future__ import annotations

from pks.models import ProjectionFilters, ProjectionSpec

CAPSULE_TYPE_PROJECTIONS: dict[str, tuple[str, ...]] = {
    "SoftwareCapsule": ("project-summary", "journal", "dev-architecture", "dev-tasks"),
    "PluginCapsule": ("project-summary", "journal", "dev-architecture"),
    "ArticleCapsule": ("project-summary", "journal", "content-outline", "content-facts"),
    "VideoCapsule": ("project-summary", "journal", "content-outline"),
    "MarketContext": ("project-summary", "market-signals", "market-narratives"),
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
        filters=ProjectionFilters(tags=["task", "todo", "in-progress", "done"]),
        order=["created_at"],
    ),
    "content-outline": ProjectionSpec(
        projection_id="content-outline",
        output_path="projections/outline.md",
        title="Outline",
        filters=ProjectionFilters(tags=["outline", "section", "structure"]),
        order=["created_at"],
    ),
    "content-facts": ProjectionSpec(
        projection_id="content-facts",
        output_path="projections/facts.md",
        title="Facts",
        filters=ProjectionFilters(types=["factual"], tags=["fact", "source"]),
        order=["created_at"],
    ),
    "research-terminology": ProjectionSpec(
        projection_id="research-terminology",
        output_path="projections/terminology.md",
        title="Terminology",
        filters=ProjectionFilters(tags=["term", "definition", "terminology"]),
        order=["created_at"],
    ),
    "research-hypotheses": ProjectionSpec(
        projection_id="research-hypotheses",
        output_path="projections/hypotheses.md",
        title="Hypotheses",
        filters=ProjectionFilters(types=["inference"], tags=["hypothesis"]),
        order=["created_at"],
    ),
    "market-signals": ProjectionSpec(
        projection_id="market-signals",
        output_path="projections/market_signals.md",
        title="Market Signals",
        description="Active factual market signals: price moves, macro releases, calendar events.",
        filters=ProjectionFilters(
            types=["factual"],
            tags=["macro", "price", "calendar", "actual_release"],
        ),
        order=["created_at"],
        group_by="predicate",
    ),
    "market-narratives": ProjectionSpec(
        projection_id="market-narratives",
        output_path="projections/market_narratives.md",
        title="Market Narratives",
        description="Active market narratives and inferences with evidence chains.",
        filters=ProjectionFilters(
            types=["inference"],
            tags=["narrative", "theme"],
        ),
        order=["created_at"],
    ),
}
def default_projection_specs(capsule_type: str) -> list[ProjectionSpec]:
    projection_ids = CAPSULE_TYPE_PROJECTIONS.get(capsule_type, ("project-summary", "journal"))
    return [PROJECTION_SPECS[projection_id] for projection_id in projection_ids]
