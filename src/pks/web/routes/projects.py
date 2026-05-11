from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from pks.web.routes.common import dump_model, kernel_from, templates_from

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    kernel = kernel_from(request)
    projects = [
        {"project": project, "health": kernel.health_check(project.project_id)}
        for project in kernel.list_capsules()
    ]
    return templates_from(request).TemplateResponse(
        request,
        "dashboard.html",
        {"projects": projects},
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(request: Request, project_id: str):
    kernel = kernel_from(request)
    project = kernel.load_capsule(project_id)
    claims = sorted(
        kernel.list_claims(project_id),
        key=lambda claim: claim.created_at,
        reverse=True,
    )
    return templates_from(request).TemplateResponse(
        request,
        "project.html",
        {
            "project": project,
            "health": kernel.health_check(project_id),
            "recent_claims": claims[:8],
            "candidate_count": len(kernel.list_candidates(project_id)),
        },
    )


@router.get("/api/projects")
def api_projects(request: Request) -> list[dict]:
    return [dump_model(project) for project in kernel_from(request).list_capsules()]


@router.get("/api/projects/{project_id}")
def api_project(request: Request, project_id: str) -> dict:
    kernel = kernel_from(request)
    return {
        "project": dump_model(kernel.load_capsule(project_id)),
        "health": dump_model(kernel.health_check(project_id)),
    }
