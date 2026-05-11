from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pks.kernel.storage import read_yaml, write_yaml
from pks.paths import resolve_pks_home

DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "capsules_dir": "capsules",
    "claim_sequence": 0,
}
DEFAULT_TOKEN_PERMISSIONS = ["read", "write"]
SUPPORTED_TOKEN_PERMISSIONS = {"read", "write"}


def mcp_config_path(home: Path | None = None) -> Path:
    return resolve_pks_home(home) / "config.yaml"


def load_mcp_config(home: Path | None = None) -> dict[str, Any]:
    path = mcp_config_path(home)
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    config = read_yaml(path)
    return config if isinstance(config, dict) else dict(DEFAULT_CONFIG)


def save_mcp_config(config: dict[str, Any], home: Path | None = None) -> None:
    resolved_home = resolve_pks_home(home)
    resolved_home.mkdir(parents=True, exist_ok=True)
    data = dict(config)
    for key, value in DEFAULT_CONFIG.items():
        data.setdefault(key, value)
    write_yaml(mcp_config_path(resolved_home), data)


def token_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    tokens = config.get("mcp_tokens") or []
    if not isinstance(tokens, list):
        return []
    return [dict(record) for record in tokens if isinstance(record, dict)]


def public_token_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "token_id": record.get("token_id"),
        "label": record.get("label"),
        "permissions": list(record.get("permissions") or []),
        "created_at": record.get("created_at"),
    }


def normalize_permissions(
    permissions: Iterable[str] | None,
    *,
    default: list[str] | None = None,
) -> list[str]:
    normalized: list[str] = []
    for item in permissions or default or DEFAULT_TOKEN_PERMISSIONS:
        permission = str(item).strip().lower()
        if permission not in SUPPORTED_TOKEN_PERMISSIONS:
            raise ValueError(f"unsupported MCP token permission: {permission}")
        if permission not in normalized:
            normalized.append(permission)
    return normalized or ["read"]
