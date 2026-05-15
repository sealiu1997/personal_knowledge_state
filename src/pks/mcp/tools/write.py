from __future__ import annotations

from typing import Any

from pks.kernel import Kernel
from pks.mcp.auth import McpTokenManager
from pks.models import ProjectMetadata, TokenPermission, TrackingConfig


def submit_candidate_claim(
    kernel: Kernel,
    token: str,
    project_id: str,
    claim: dict[str, Any],
) -> dict[str, Any]:
    token_hash = McpTokenManager.hash_token(token)
    permission = kernel.validate_token(token_hash)
    if permission != TokenPermission.WRITE.value:
        raise PermissionError("valid write token required")
    data = dict(claim)
    data.setdefault("created_by", "agent:mcp")
    decision = kernel.submit_candidate_draft(project_id, data)
    return decision.model_dump(mode="json")


def create_capsule(
    kernel: Kernel,
    token: str,
    project_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    _require_write_token(kernel, token)
    project = _project_metadata(project_id, metadata)
    capsule_path = kernel.create_capsule(project)
    return {
        "project": project.model_dump(mode="json"),
        "capsule_path": str(capsule_path),
    }


def verify_claim(
    kernel: Kernel,
    token: str,
    project_id: str,
    claim_id: str,
) -> dict[str, Any]:
    _require_write_token(kernel, token)
    return kernel.verify_claim(project_id, claim_id).model_dump(mode="json")


def _require_write_token(kernel: Kernel, token: str) -> None:
    token_hash = McpTokenManager.hash_token(token)
    permission = kernel.validate_token(token_hash)
    if permission != TokenPermission.WRITE.value:
        raise PermissionError("valid write token required")


def _project_metadata(project_id: str, metadata: dict[str, Any]) -> ProjectMetadata:
    data = dict(metadata)
    data["project_id"] = project_id
    project_path = data.pop("project_path", None)
    git_remote = data.pop("git_remote", None)
    watched_paths = data.pop("watched_paths", None)
    if project_path is not None and "external_project_path" not in data:
        data["external_project_path"] = project_path
    if git_remote is not None and "repository_url" not in data:
        data["repository_url"] = git_remote
    tracking = data.get("tracking") if isinstance(data.get("tracking"), dict) else {}
    if project_path is not None and "project_path" not in tracking:
        tracking["project_path"] = project_path
    if git_remote is not None and "git_remote" not in tracking:
        tracking["git_remote"] = git_remote
    if watched_paths is not None and "watched_paths" not in tracking:
        tracking["watched_paths"] = _normalize_string_list(watched_paths)
    if tracking:
        data["tracking"] = TrackingConfig.model_validate(tracking)
    return ProjectMetadata.model_validate(data)


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []
