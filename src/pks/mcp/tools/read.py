from __future__ import annotations

from typing import Any

from pks.kernel import Kernel


def get_project_context(kernel: Kernel, project_id: str) -> str:
    return kernel.render_context(project_id)


def search_claims(
    kernel: Kernel,
    project_id: str,
    *,
    status: str | None = None,
    type: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    subject: str | None = None,
    predicate: str | None = None,
    projection: str | None = None,
) -> list[dict[str, Any]]:
    claims = kernel.list_claims(
        project_id,
        status=status,
        type=type,
        domain=domain,
        tag=tag,
        subject=subject,
        predicate=predicate,
        projection=projection,
    )
    return [claim.model_dump(mode="json") for claim in claims]


def get_claim(kernel: Kernel, project_id: str, claim_id: str) -> dict[str, Any]:
    return kernel.load_claim(project_id, claim_id).model_dump(mode="json")


def get_health(kernel: Kernel, project_id: str) -> dict[str, Any]:
    return kernel.health_check(project_id).model_dump(mode="json")


def get_reverification_issues(kernel: Kernel, project_id: str) -> list[dict[str, Any]]:
    return [
        issue.model_dump(mode="json")
        for issue in kernel.health_check(project_id).reverification_issues
    ]


def list_projects(kernel: Kernel) -> list[dict[str, Any]]:
    return [project.model_dump(mode="json") for project in kernel.list_capsules()]
