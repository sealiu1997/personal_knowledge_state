from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pks.web.routes.claims_helpers import evidence_tree, projection_for_claim
from pks.web.routes.common import dump_model, kernel_from

router = APIRouter()


@router.get("/api/projects/{project_id}/claims")
def api_claims(
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
) -> list[dict]:
    claims = kernel_from(request).list_claims(
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
    return [dump_model(claim) for claim in claims]


@router.post("/api/projects/{project_id}/claims")
async def api_create_claim(request: Request, project_id: str) -> JSONResponse:
    payload = await request.json()
    decision = kernel_from(request).submit_candidate_draft(project_id, payload)
    status_code = 422 if decision.action == "reject" else 201
    return JSONResponse(dump_model(decision), status_code=status_code)


@router.get("/api/projects/{project_id}/claims/{claim_id}")
def api_claim(request: Request, project_id: str, claim_id: str) -> dict:
    return dump_model(kernel_from(request).load_claim(project_id, claim_id))


@router.post("/api/projects/{project_id}/claims/{claim_id}/patch")
async def api_patch_claim(request: Request, project_id: str, claim_id: str) -> dict:
    kernel = kernel_from(request)
    payload = await request.json()
    changes = payload.get("changes", {}) if isinstance(payload, dict) else {}
    projection_id = payload.get("projection") if isinstance(payload, dict) else None
    if not projection_id:
        claim = kernel.load_claim(project_id, claim_id)
        projection_id = projection_for_claim(kernel, project_id, claim)
    result = kernel.patch_projection_claim(project_id, projection_id, claim_id, changes)
    return dump_model(result)


@router.post("/api/projects/{project_id}/claims/{claim_id}/verify")
def api_verify_claim(request: Request, project_id: str, claim_id: str) -> dict:
    return dump_model(kernel_from(request).verify_claim(project_id, claim_id))


@router.post("/api/projects/{project_id}/claims/{claim_id}/expire")
def api_expire_claim(request: Request, project_id: str, claim_id: str) -> dict:
    return dump_model(kernel_from(request).expire_claim(project_id, claim_id))


@router.get("/api/projects/{project_id}/claims/{claim_id}/evidence-tree")
def api_evidence_tree(request: Request, project_id: str, claim_id: str) -> dict:
    kernel = kernel_from(request)
    claim = kernel.load_claim(project_id, claim_id)
    return evidence_tree(kernel, project_id, claim)
