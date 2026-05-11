from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from pks.web.routes.common import dump_model, kernel_from, templates_from

router = APIRouter()


@router.get("/projects/{project_id}/claims", response_class=HTMLResponse)
def claims_browser(
    request: Request,
    project_id: str,
    status: str | None = None,
    type: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
):
    kernel = kernel_from(request)
    claims = kernel.list_claims(
        project_id,
        status=status,
        type=type,
        domain=domain,
        tag=tag,
    )
    return templates_from(request).TemplateResponse(
        request,
        "claims.html",
        {
            "project": kernel.load_capsule(project_id),
            "claims": claims,
            "filters": {"status": status, "type": type, "domain": domain, "tag": tag},
        },
    )


@router.get("/projects/{project_id}/claims/{claim_id}", response_class=HTMLResponse)
def claim_detail(request: Request, project_id: str, claim_id: str):
    kernel = kernel_from(request)
    return templates_from(request).TemplateResponse(
        request,
        "claim.html",
        {
            "project": kernel.load_capsule(project_id),
            "claim": kernel.load_claim(project_id, claim_id),
        },
    )


@router.get("/api/projects/{project_id}/claims")
def api_claims(
    request: Request,
    project_id: str,
    status: str | None = None,
    type: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    claims = kernel_from(request).list_claims(
        project_id,
        status=status,
        type=type,
        domain=domain,
        tag=tag,
    )
    return [dump_model(claim) for claim in claims]


@router.get("/api/projects/{project_id}/claims/{claim_id}")
def api_claim(request: Request, project_id: str, claim_id: str) -> dict:
    return dump_model(kernel_from(request).load_claim(project_id, claim_id))
