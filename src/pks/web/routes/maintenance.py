from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from pks.web.routes.common import dump_model, kernel_from

router = APIRouter()


@router.post("/projects/{project_id}/maintain")
def maintain_project_page(project_id: str, request: Request):
    kernel_from(request).maintenance.run_all(project_id)
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


@router.post("/api/projects/{project_id}/maintain")
def api_maintain_project(
    request: Request,
    project_id: str,
    stale: bool = True,
    expiry: bool = True,
    evidence: bool = True,
) -> dict:
    report = kernel_from(request).maintenance.run(
        project_id,
        stale=stale,
        expiry=expiry,
        evidence=evidence,
    )
    return dump_model(report)
