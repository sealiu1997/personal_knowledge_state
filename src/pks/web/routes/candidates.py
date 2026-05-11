from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from pks.web.routes.common import dump_model, kernel_from, templates_from

router = APIRouter()


@router.get("/projects/{project_id}/review", response_class=HTMLResponse)
def review_workbench(request: Request, project_id: str):
    kernel = kernel_from(request)
    candidates = [
        {"claim": claim, "decision": kernel.review_candidate(project_id, claim.claim_id)}
        for claim in kernel.list_candidates(project_id)
    ]
    return templates_from(request).TemplateResponse(
        request,
        "review.html",
        {"project": kernel.load_capsule(project_id), "candidates": candidates},
    )


@router.get("/projects/{project_id}/review/{candidate_id}", response_class=HTMLResponse)
def candidate_detail(request: Request, project_id: str, candidate_id: str):
    kernel = kernel_from(request)
    return templates_from(request).TemplateResponse(
        request,
        "candidate.html",
        {
            "project": kernel.load_capsule(project_id),
            "claim": kernel.load_candidate(project_id, candidate_id),
            "decision": kernel.review_candidate(project_id, candidate_id),
        },
    )


@router.post("/projects/{project_id}/review/{candidate_id}/accept")
def accept_candidate_page(project_id: str, candidate_id: str, request: Request):
    kernel_from(request).accept_candidate(project_id, candidate_id)
    return RedirectResponse(f"/projects/{project_id}/review", status_code=303)


@router.post("/projects/{project_id}/review/{candidate_id}/reject")
def reject_candidate_page(project_id: str, candidate_id: str, request: Request):
    kernel_from(request).reject_candidate(project_id, candidate_id)
    return RedirectResponse(f"/projects/{project_id}/review", status_code=303)


@router.post("/projects/{project_id}/review/batch-accept")
async def batch_accept_page(project_id: str, request: Request):
    ids = await _ids_from_form(request)
    _batch_accept(kernel_from(request), project_id, ids)
    return RedirectResponse(f"/projects/{project_id}/review", status_code=303)


@router.post("/projects/{project_id}/review/batch-reject")
async def batch_reject_page(project_id: str, request: Request):
    ids = await _ids_from_form(request)
    _batch_reject(kernel_from(request), project_id, ids)
    return RedirectResponse(f"/projects/{project_id}/review", status_code=303)


@router.get("/api/projects/{project_id}/candidates")
def api_candidates(request: Request, project_id: str) -> list[dict]:
    return [dump_model(claim) for claim in kernel_from(request).list_candidates(project_id)]


@router.get("/api/projects/{project_id}/candidates/{candidate_id}")
def api_candidate(request: Request, project_id: str, candidate_id: str) -> dict:
    kernel = kernel_from(request)
    return {
        "candidate": dump_model(kernel.load_candidate(project_id, candidate_id)),
        "review": dump_model(kernel.review_candidate(project_id, candidate_id)),
    }


@router.post("/api/projects/{project_id}/candidates/{candidate_id}/accept")
def api_accept_candidate(request: Request, project_id: str, candidate_id: str) -> dict:
    return dump_model(kernel_from(request).accept_candidate(project_id, candidate_id))


@router.post("/api/projects/{project_id}/candidates/{candidate_id}/reject")
def api_reject_candidate(request: Request, project_id: str, candidate_id: str) -> dict:
    return dump_model(kernel_from(request).reject_candidate(project_id, candidate_id))


@router.post("/api/projects/{project_id}/candidates/batch-accept")
async def api_batch_accept_candidate(request: Request, project_id: str) -> dict:
    ids = await _ids_from_json(request)
    return _batch_accept(kernel_from(request), project_id, ids)


@router.post("/api/projects/{project_id}/candidates/batch-reject")
async def api_batch_reject_candidate(request: Request, project_id: str) -> dict:
    ids = await _ids_from_json(request)
    return _batch_reject(kernel_from(request), project_id, ids)


def _batch_accept(kernel, project_id: str, ids: list[str]) -> dict:
    accepted: list[str] = []
    failed: list[dict[str, str]] = []
    for candidate_id in ids:
        try:
            kernel.accept_candidate(project_id, candidate_id)
            accepted.append(candidate_id)
        except Exception as exc:  # noqa: BLE001 - batch API should report per-item failures
            failed.append({"id": candidate_id, "reason": str(exc)})
    return {"accepted": accepted, "failed": failed}


def _batch_reject(kernel, project_id: str, ids: list[str]) -> dict:
    rejected: list[str] = []
    failed: list[dict[str, str]] = []
    for candidate_id in ids:
        try:
            kernel.reject_candidate(project_id, candidate_id)
            rejected.append(candidate_id)
        except Exception as exc:  # noqa: BLE001 - batch API should report per-item failures
            failed.append({"id": candidate_id, "reason": str(exc)})
    return {"rejected": rejected, "failed": failed}


async def _ids_from_json(request: Request) -> list[str]:
    payload = await request.json()
    ids = payload.get("ids", []) if isinstance(payload, dict) else []
    return [str(item).strip() for item in ids if str(item).strip()]


async def _ids_from_form(request: Request) -> list[str]:
    body = (await request.body()).decode("utf-8")
    values = parse_qs(body).get("ids", [])
    return [item.strip() for item in values if item.strip()]
