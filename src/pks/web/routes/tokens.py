from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from pks.mcp.auth import McpTokenManager
from pks.mcp.config import DEFAULT_TOKEN_PERMISSIONS
from pks.web.routes.common import templates_from

router = APIRouter()


@router.get("/tokens", response_class=HTMLResponse)
def token_page(request: Request):
    manager = _manager(request)
    return templates_from(request).TemplateResponse(
        request,
        "tokens.html",
        {"tokens": manager.list_tokens(), "created": None},
    )


@router.post("/tokens")
async def token_create_page(request: Request):
    payload = await _request_data(request)
    created = _manager(request).create_token(
        str(payload.get("label") or "MCP token"),
        ["write"],
    )
    return templates_from(request).TemplateResponse(
        request,
        "tokens.html",
        {"tokens": _manager(request).list_tokens(), "created": created},
    )


@router.post("/tokens/{token_id}/revoke")
def token_revoke_page(request: Request, token_id: str):
    _manager(request).revoke_token(token_id)
    return RedirectResponse("/tokens", status_code=303)


@router.post("/tokens/{token_id}/regenerate")
def token_regenerate_page(request: Request, token_id: str):
    created = _manager(request).regenerate_token(token_id)
    return templates_from(request).TemplateResponse(
        request,
        "tokens.html",
        {"tokens": _manager(request).list_tokens(), "created": created},
    )


@router.get("/api/mcp/tokens")
def api_tokens(request: Request) -> list[dict[str, Any]]:
    return _manager(request).list_tokens()


@router.post("/api/mcp/tokens")
async def api_token_create(request: Request) -> dict[str, Any]:
    payload = await _request_data(request)
    return _manager(request).create_token(
        str(payload.get("label") or "MCP token"),
        _permissions_from_payload(payload),
    )


@router.delete("/api/mcp/tokens/{token_id}")
def api_token_revoke(request: Request, token_id: str) -> dict[str, Any]:
    return _manager(request).revoke_token(token_id)


@router.post("/api/mcp/tokens/{token_id}/regenerate")
def api_token_regenerate(request: Request, token_id: str) -> dict[str, Any]:
    return _manager(request).regenerate_token(token_id)


def _manager(request: Request) -> McpTokenManager:
    return McpTokenManager(request.app.state.kernel.home)


async def _request_data(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        return payload if isinstance(payload, dict) else {}
    body = (await request.body()).decode("utf-8")
    from urllib.parse import parse_qs

    parsed = parse_qs(body)
    return {key: values[0] for key, values in parsed.items() if values}


def _permissions_from_payload(payload: dict[str, Any]) -> list[str]:
    value = payload.get("permissions")
    if value is None:
        return DEFAULT_TOKEN_PERMISSIONS
    if isinstance(value, list):
        return [str(item) for item in value]
    return [item.strip() for item in str(value).split(",") if item.strip()]
