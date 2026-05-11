from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from pks.models import ReviewDecision
from pks.web.routes.claims_helpers import (
    claim_form_data,
    evidence_tree,
    form_values,
    patch_changes,
    projection_for_claim,
)
from pks.web.routes.common import kernel_from, templates_from

router = APIRouter()


@router.get("/projects/{project_id}/claims", response_class=HTMLResponse)
def claims_browser(
    request: Request,
    project_id: str,
    status: str | None = None,
    type: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    subject: str | None = None,
    predicate: str | None = None,
    projection: str | None = None,
    sort: str | None = None,
):
    kernel = kernel_from(request)
    claims = kernel.list_claims(
        project_id,
        status=status,
        type=type,
        domain=domain,
        tag=tag,
        subject=subject,
        predicate=predicate,
        projection=projection,
        sort=sort,
    )
    return templates_from(request).TemplateResponse(
        request,
        "claims.html",
        {
            "project": kernel.load_capsule(project_id),
            "claims": claims,
            "projections": kernel.list_projections(project_id),
            "filters": {
                "status": status,
                "type": type,
                "domain": domain,
                "tag": tag,
                "subject": subject,
                "predicate": predicate,
                "projection": projection,
                "sort": sort,
            },
        },
    )


@router.get("/projects/{project_id}/claims/new", response_class=HTMLResponse)
def claim_new(request: Request, project_id: str):
    kernel = kernel_from(request)
    return templates_from(request).TemplateResponse(
        request,
        "claim_form.html",
        {
            "project": kernel.load_capsule(project_id),
            "claim": None,
            "accepted_claims": kernel.list_claims(project_id, status="accepted"),
            "projections": kernel.list_projections(project_id),
            "action": f"/projects/{project_id}/claims/new",
            "mode": "new",
            "decision": None,
        },
    )


@router.post("/projects/{project_id}/claims/new")
async def claim_create_page(request: Request, project_id: str):
    kernel = kernel_from(request)
    data = await claim_form_data(request)
    decision = kernel.submit_candidate_draft(project_id, data)
    if decision.action == "reject":
        return templates_from(request).TemplateResponse(
            request,
            "claim_form.html",
            {
                "project": kernel.load_capsule(project_id),
                "claim": None,
                "accepted_claims": kernel.list_claims(project_id, status="accepted"),
                "projections": kernel.list_projections(project_id),
                "action": f"/projects/{project_id}/claims/new",
                "mode": "new",
                "decision": decision,
                "draft": data,
            },
            status_code=422,
        )
    return RedirectResponse(f"/projects/{project_id}/review", status_code=303)


@router.get("/projects/{project_id}/claims/{claim_id}", response_class=HTMLResponse)
def claim_detail(request: Request, project_id: str, claim_id: str):
    kernel = kernel_from(request)
    claim = kernel.load_claim(project_id, claim_id)
    return templates_from(request).TemplateResponse(
        request,
        "claim.html",
        {
            "project": kernel.load_capsule(project_id),
            "claim": claim,
            "projection_id": projection_for_claim(kernel, project_id, claim),
        },
    )


@router.get("/projects/{project_id}/claims/{claim_id}/edit", response_class=HTMLResponse)
def claim_edit(request: Request, project_id: str, claim_id: str):
    kernel = kernel_from(request)
    claim = kernel.load_claim(project_id, claim_id)
    return templates_from(request).TemplateResponse(
        request,
        "claim_form.html",
        {
            "project": kernel.load_capsule(project_id),
            "claim": claim,
            "accepted_claims": kernel.list_claims(project_id, status="accepted"),
            "projections": kernel.list_projections(project_id),
            "action": f"/projects/{project_id}/claims/{claim_id}/edit",
            "mode": "edit",
            "projection_id": projection_for_claim(kernel, project_id, claim),
            "decision": None,
        },
    )


@router.post("/projects/{project_id}/claims/{claim_id}/edit")
async def claim_edit_page(request: Request, project_id: str, claim_id: str):
    kernel = kernel_from(request)
    body = await form_values(request)
    projection_id = body.get("projection", [""])[0].strip() or projection_for_claim(
        kernel,
        project_id,
        kernel.load_claim(project_id, claim_id),
    )
    result = kernel.patch_projection_claim(
        project_id,
        projection_id,
        claim_id,
        patch_changes(body),
    )
    if isinstance(result, ReviewDecision):
        return RedirectResponse(f"/projects/{project_id}/review", status_code=303)
    return RedirectResponse(f"/projects/{project_id}/claims/{claim_id}", status_code=303)


@router.get("/projects/{project_id}/claims/{claim_id}/evidence-tree", response_class=HTMLResponse)
def claim_evidence_tree(request: Request, project_id: str, claim_id: str):
    kernel = kernel_from(request)
    claim = kernel.load_claim(project_id, claim_id)
    return templates_from(request).TemplateResponse(
        request,
        "evidence_tree.html",
        {
            "project": kernel.load_capsule(project_id),
            "claim": claim,
            "tree": evidence_tree(kernel, project_id, claim),
        },
    )
