from __future__ import annotations

from typing import Any

from pks.kernel import Kernel
from pks.mcp.auth import McpTokenManager
from pks.models import TokenPermission


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


def verify_claim(
    kernel: Kernel,
    token: str,
    project_id: str,
    claim_id: str,
) -> dict[str, Any]:
    token_hash = McpTokenManager.hash_token(token)
    permission = kernel.validate_token(token_hash)
    if permission != TokenPermission.WRITE.value:
        raise PermissionError("valid write token required")
    return kernel.verify_claim(project_id, claim_id).model_dump(mode="json")
