from __future__ import annotations

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from pks.web.routes.common import dump_model, kernel_from, templates_from

router = APIRouter()


@router.get("/projects/{project_id}/config", response_class=HTMLResponse)
def config_page(request: Request, project_id: str):
    kernel = kernel_from(request)
    project = kernel.load_capsule(project_id)
    policy = kernel.load_policy(project.domain_value)
    return templates_from(request).TemplateResponse(
        request,
        "config.html",
        {
            "project": project,
            "policy": policy,
            "policy_yaml": yaml.safe_dump(
                policy.model_dump(mode="json"),
                allow_unicode=True,
                sort_keys=False,
            ),
            "projections": kernel.list_projections(project_id),
        },
    )


@router.post("/projects/{project_id}/config")
async def config_update_page(request: Request, project_id: str):
    kernel = kernel_from(request)
    project = kernel.load_capsule(project_id)
    body = (await request.body()).decode("utf-8")
    from urllib.parse import parse_qs

    values = parse_qs(body)
    policy_yaml = (values.get("policy_yaml") or [""])[0]
    policy_data = yaml.safe_load(policy_yaml) or {}
    kernel.update_policy(project.domain_value, policy_data)
    return RedirectResponse(f"/projects/{project_id}/config", status_code=303)


@router.get("/api/projects/{project_id}/policy")
def api_policy(request: Request, project_id: str) -> dict:
    kernel = kernel_from(request)
    project = kernel.load_capsule(project_id)
    return dump_model(kernel.load_policy(project.domain_value))


@router.post("/api/projects/{project_id}/policy")
async def api_policy_update(request: Request, project_id: str) -> dict:
    kernel = kernel_from(request)
    project = kernel.load_capsule(project_id)
    payload = await request.json()
    return dump_model(kernel.update_policy(project.domain_value, payload))


@router.get("/api/projects/{project_id}/projection-specs")
def api_projection_specs(request: Request, project_id: str) -> list[dict]:
    return [dump_model(spec) for spec in kernel_from(request).list_projections(project_id)]
