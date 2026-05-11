from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from pks.models import ProjectionFilters, ProjectionSpec
from pks.web.routes.common import dump_model, kernel_from, templates_from

router = APIRouter()


@router.get("/projects/{project_id}/projections", response_class=HTMLResponse)
def projection_list_page(request: Request, project_id: str):
    kernel = kernel_from(request)
    return templates_from(request).TemplateResponse(
        request,
        "projections.html",
        {
            "project": kernel.load_capsule(project_id),
            "projections": _projection_summaries(kernel, project_id),
        },
    )


@router.get("/projects/{project_id}/projections/new", response_class=HTMLResponse)
def projection_new_page(request: Request, project_id: str):
    kernel = kernel_from(request)
    return templates_from(request).TemplateResponse(
        request,
        "projection_form.html",
        {
            "project": kernel.load_capsule(project_id),
            "spec": None,
            "is_custom": True,
            "mode": "new",
            "action": f"/projects/{project_id}/projections/new",
            "preview": None,
        },
    )


@router.post("/projects/{project_id}/projections/new")
async def projection_create_page(request: Request, project_id: str):
    kernel = kernel_from(request)
    spec = ProjectionSpec.model_validate(await _projection_form_data(request))
    try:
        kernel.create_projection_spec(project_id, spec)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RedirectResponse(
        f"/projects/{project_id}/projections/{spec.projection_id}",
        status_code=303,
    )


@router.get("/projects/{project_id}/projections/{projection_id}", response_class=HTMLResponse)
def projection_preview_page(request: Request, project_id: str, projection_id: str):
    kernel = kernel_from(request)
    spec = kernel.load_projection_spec(project_id, projection_id)
    markdown = kernel.render_projection(project_id, projection_id=projection_id)
    claims = kernel.list_claims(project_id, projection=projection_id)
    return templates_from(request).TemplateResponse(
        request,
        "projection_preview.html",
        {
            "project": kernel.load_capsule(project_id),
            "spec": spec,
            "markdown": markdown,
            "claims": claims,
            "is_custom": projection_id in kernel.list_custom_projection_ids(project_id),
        },
    )


@router.post("/projects/{project_id}/projections/{projection_id}/write")
def projection_write_page(project_id: str, projection_id: str, request: Request):
    kernel_from(request).render_projection(project_id, projection_id=projection_id, write=True)
    return RedirectResponse(f"/projects/{project_id}/projections/{projection_id}", status_code=303)


@router.get("/projects/{project_id}/projections/{projection_id}/edit", response_class=HTMLResponse)
def projection_edit_page(request: Request, project_id: str, projection_id: str):
    kernel = kernel_from(request)
    spec = kernel.load_projection_spec(project_id, projection_id)
    preview = kernel.preview_projection_spec(project_id, spec)
    return templates_from(request).TemplateResponse(
        request,
        "projection_form.html",
        {
            "project": kernel.load_capsule(project_id),
            "spec": spec,
            "is_custom": projection_id in kernel.list_custom_projection_ids(project_id),
            "mode": "edit",
            "action": f"/projects/{project_id}/projections/{projection_id}/edit",
            "preview": preview,
        },
    )


@router.post("/projects/{project_id}/projections/{projection_id}/edit")
async def projection_update_page(request: Request, project_id: str, projection_id: str):
    kernel = kernel_from(request)
    existing = kernel.load_projection_spec(project_id, projection_id)
    is_custom = projection_id in kernel.list_custom_projection_ids(project_id)
    form_data = await _projection_form_data(request, existing=existing, is_custom=is_custom)
    form_data.pop("projection_id", None)
    kernel.update_projection_spec(project_id, projection_id, form_data)
    return RedirectResponse(f"/projects/{project_id}/projections/{projection_id}", status_code=303)


@router.post("/projects/{project_id}/projections/{projection_id}/delete")
def projection_delete_page(request: Request, project_id: str, projection_id: str):
    kernel = kernel_from(request)
    try:
        kernel.delete_projection_spec(project_id, projection_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(f"/projects/{project_id}/projections", status_code=303)


@router.get("/projects/{project_id}/pks-md", response_class=HTMLResponse)
def pks_md_preview_page(request: Request, project_id: str):
    kernel = kernel_from(request)
    return templates_from(request).TemplateResponse(
        request,
        "pks_md.html",
        {
            "project": kernel.load_capsule(project_id),
            "markdown": kernel.render_context(project_id),
        },
    )


@router.post("/projects/{project_id}/pks-md/write")
def pks_md_write_page(request: Request, project_id: str):
    kernel_from(request).render_projection(project_id, write=True)
    return RedirectResponse(f"/projects/{project_id}/pks-md", status_code=303)


@router.get("/api/projects/{project_id}/projections")
def api_projections(request: Request, project_id: str) -> list[dict[str, Any]]:
    return _projection_summaries(kernel_from(request), project_id)


@router.post("/api/projects/{project_id}/projections")
async def api_create_projection(request: Request, project_id: str) -> dict:
    spec = ProjectionSpec.model_validate(await request.json())
    try:
        return dump_model(kernel_from(request).create_projection_spec(project_id, spec))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/projects/{project_id}/projections/preview")
async def api_preview_new_projection(request: Request, project_id: str) -> dict:
    spec = ProjectionSpec.model_validate(await request.json())
    return kernel_from(request).preview_projection_spec(project_id, spec)


@router.get("/api/projects/{project_id}/projections/{projection_id}")
def api_projection(request: Request, project_id: str, projection_id: str) -> dict:
    return dump_model(kernel_from(request).load_projection_spec(project_id, projection_id))


@router.post("/api/projects/{project_id}/projections/{projection_id}")
async def api_update_projection(request: Request, project_id: str, projection_id: str) -> dict:
    payload = await request.json()
    if not isinstance(payload, dict):
        return {}
    payload.pop("projection_id", None)
    updated = kernel_from(request).update_projection_spec(project_id, projection_id, payload)
    return dump_model(updated)


@router.delete("/api/projects/{project_id}/projections/{projection_id}")
def api_delete_projection(request: Request, project_id: str, projection_id: str) -> dict:
    try:
        kernel_from(request).delete_projection_spec(project_id, projection_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"projection_id": projection_id, "deleted": True}


@router.get("/api/projects/{project_id}/projections/{projection_id}/render")
def api_render_projection(request: Request, project_id: str, projection_id: str) -> dict:
    markdown = kernel_from(request).render_projection(project_id, projection_id=projection_id)
    return {"markdown": markdown}


@router.get("/api/projects/{project_id}/projections/{projection_id}/claims")
def api_projection_claims(request: Request, project_id: str, projection_id: str) -> list[dict]:
    claims = kernel_from(request).list_claims(project_id, projection=projection_id)
    return [dump_model(claim) for claim in claims]


@router.post("/api/projects/{project_id}/projections/{projection_id}/write")
def api_write_projection(request: Request, project_id: str, projection_id: str) -> dict:
    path = kernel_from(request).render_projection(
        project_id,
        projection_id=projection_id,
        write=True,
    )
    return {"path": str(path)}


@router.post("/api/projects/{project_id}/projections/{projection_id}/preview")
async def api_preview_projection(request: Request, project_id: str, projection_id: str) -> dict:
    kernel = kernel_from(request)
    existing = kernel.load_projection_spec(project_id, projection_id)
    payload = await request.json()
    spec = _spec_with_changes(existing, payload if isinstance(payload, dict) else {})
    return kernel.preview_projection_spec(project_id, spec)


@router.get("/api/projects/{project_id}/pks-md")
def api_pks_md(request: Request, project_id: str) -> dict:
    return {"markdown": kernel_from(request).render_context(project_id)}


@router.post("/api/projects/{project_id}/pks-md/write")
def api_write_pks_md(request: Request, project_id: str) -> dict:
    path = kernel_from(request).render_projection(project_id, write=True)
    return {"path": str(path)}


def _projection_summaries(kernel, project_id: str) -> list[dict[str, Any]]:
    custom_ids = kernel.list_custom_projection_ids(project_id)
    summaries = []
    for spec in kernel.list_projections(project_id):
        count = len(kernel.list_claims(project_id, projection=spec.projection_id))
        summaries.append(
            {
                **dump_model(spec),
                "claim_count": count,
                "kind": "custom" if spec.projection_id in custom_ids else "built-in",
            }
        )
    return summaries


async def _projection_form_data(
    request: Request,
    existing: ProjectionSpec | None = None,
    is_custom: bool = True,
) -> dict[str, Any]:
    values = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    projection_id = existing.projection_id if existing else ""
    data: dict[str, Any] = {
        "projection_id": _value(values, "projection_id") or projection_id,
        "output_path": _value(values, "output_path") or (existing.output_path if existing else ""),
        "title": _value(values, "title") or (existing.title if existing else ""),
        "description": _value(values, "description") or None,
        "include_status": _list(values, "include_status"),
        "exclude_stale": _value(values, "exclude_stale") == "true",
        "filters": {
            "types": _list(values, "filter_types"),
            "tags": _csv(values, "filter_tags"),
            "predicates": _csv(values, "filter_predicates"),
            "exclude_tags": _csv(values, "filter_exclude_tags"),
        },
        "order": _list(values, "order") or ["type", "created_at"],
    }
    if existing and not is_custom:
        data["projection_id"] = existing.projection_id
        data["output_path"] = existing.output_path
    return data


def _spec_with_changes(existing: ProjectionSpec, changes: dict[str, Any]) -> ProjectionSpec:
    data = existing.model_dump(mode="python")
    data.update({key: value for key, value in changes.items() if key != "projection_id"})
    data["projection_id"] = existing.projection_id
    data["output_path"] = existing.output_path
    if "filters" in changes:
        data["filters"] = ProjectionFilters.model_validate(changes["filters"])
    return ProjectionSpec.model_validate(data)


def _value(values: dict[str, list[str]], key: str) -> str:
    return (values.get(key) or [""])[0].strip()


def _list(values: dict[str, list[str]], key: str) -> list[str]:
    return [item.strip() for item in values.get(key, []) if item.strip()]


def _csv(values: dict[str, list[str]], key: str) -> list[str]:
    return [item.strip() for item in _value(values, key).split(",") if item.strip()]
