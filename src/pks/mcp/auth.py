from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pks.mcp.config import (
    DEFAULT_TOKEN_PERMISSIONS,
    load_mcp_config,
    normalize_permissions,
    public_token_record,
    save_mcp_config,
    token_records,
)


class McpTokenManager:
    def __init__(self, home: Path | None = None) -> None:
        self.home = home

    def create_token(
        self,
        label: str,
        permissions: list[str] | None = None,
    ) -> dict[str, Any]:
        label = label.strip() or "MCP token"
        permissions = normalize_permissions(permissions)
        token = f"pks_{secrets.token_urlsafe(32)}"
        token_id = f"tok_{secrets.token_hex(6)}"
        record = {
            "token_id": token_id,
            "token_hash": self.hash_token(token),
            "created_at": datetime.now(UTC).isoformat(),
            "label": label,
            "permissions": permissions,
        }
        config = load_mcp_config(self.home)
        tokens = token_records(config)
        tokens.append(record)
        config["mcp_tokens"] = tokens
        save_mcp_config(config, self.home)
        return {
            "token_id": token_id,
            "token": token,
            "label": label,
            "permissions": permissions,
            "created_at": record["created_at"],
        }

    def list_tokens(self) -> list[dict[str, Any]]:
        return [public_token_record(record) for record in token_records(load_mcp_config(self.home))]

    def revoke_token(self, token_id: str) -> dict[str, Any]:
        config = load_mcp_config(self.home)
        tokens = token_records(config)
        remaining = [record for record in tokens if record.get("token_id") != token_id]
        if len(remaining) == len(tokens):
            raise KeyError(f"unknown token: {token_id}")
        config["mcp_tokens"] = remaining
        save_mcp_config(config, self.home)
        return {"token_id": token_id, "revoked": True}

    def regenerate_token(self, token_id: str) -> dict[str, Any]:
        record = self._find_record(token_id)
        self.revoke_token(token_id)
        return self.create_token(
            str(record.get("label") or "MCP token"),
            list(record.get("permissions") or DEFAULT_TOKEN_PERMISSIONS),
        )

    def permission_for_hash(self, token_hash: str) -> str:
        for record in token_records(load_mcp_config(self.home)):
            if record.get("token_hash") != token_hash:
                continue
            permissions = set(record.get("permissions") or [])
            if "write" in permissions:
                return "write"
            if "read" in permissions:
                return "read"
        return "invalid"

    @staticmethod
    def hash_token(token: str) -> str:
        return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _find_record(self, token_id: str) -> dict[str, Any]:
        for record in token_records(load_mcp_config(self.home)):
            if record.get("token_id") == token_id:
                return record
        raise KeyError(f"unknown token: {token_id}")
