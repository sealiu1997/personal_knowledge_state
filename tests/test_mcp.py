from datetime import date

import pytest

from pks.kernel import Kernel
from pks.mcp.auth import McpTokenManager
from pks.mcp.tools.read import get_reverification_issues, list_projects
from pks.mcp.tools.write import submit_candidate_claim, verify_claim
from pks.models import (
    CapsuleDomain,
    Claim,
    ClaimType,
    ProjectMetadata,
    SupportingClaim,
    TokenPermission,
)


def project() -> ProjectMetadata:
    return ProjectMetadata(
        project_id="pks",
        name="PKS",
        capsule_type="SoftwareCapsule",
        domain=CapsuleDomain.DEV,
        stage="P3",
    )


def claim_payload() -> dict:
    return {
        "subject": "PKS MCP",
        "predicate": "submits",
        "object": "candidate claims",
        "type": "factual",
        "tags": ["mcp"],
        "confidence": 0.9,
        "evidence": [
            {
                "source_ref": "manual",
                "relation": "supports",
                "excerpt": "MCP tool test",
            }
        ],
    }


def test_mcp_tokens_store_hash_and_kernel_validates_permission(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    manager = McpTokenManager(home)

    created = manager.create_token("Codex", ["read", "write"])
    listed = manager.list_tokens()
    token_hash = McpTokenManager.hash_token(created["token"])

    assert "token" not in listed[0]
    assert created["token"] not in (home / "config.yaml").read_text(encoding="utf-8")
    assert kernel.validate_token(token_hash) == TokenPermission.WRITE

    manager.revoke_token(created["token_id"])

    assert kernel.validate_token(token_hash) == TokenPermission.INVALID


def test_mcp_read_and_write_tools_use_kernel_and_token_gate(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    token = McpTokenManager(home).create_token("Agent", ["read", "write"])

    projects = list_projects(kernel)
    decision = submit_candidate_claim(kernel, token["token"], "pks", claim_payload())
    candidates = kernel.list_candidates("pks")

    assert projects[0]["project_id"] == "pks"
    assert decision["action"] == "auto_accept"
    assert candidates[0].claim_id.startswith("F-")
    assert candidates[0].created_by == "agent:mcp"


def test_mcp_write_tool_rejects_invalid_token(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())

    with pytest.raises(PermissionError):
        submit_candidate_claim(kernel, "bad-token", "pks", claim_payload())


def test_mcp_reverification_tools_list_and_verify_with_token(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    token = McpTokenManager(home).create_token("Agent", ["read", "write"])
    submit_candidate_claim(kernel, token["token"], "pks", claim_payload())
    support_id = kernel.list_candidates("pks")[0].claim_id
    kernel.accept_candidate("pks", support_id)
    dependent = Claim(
        claim_id="I-MCP-DEPENDS",
        subject="PKS MCP",
        predicate="depends_on",
        object="accepted facts",
        type=ClaimType.INFERENCE,
        domain=CapsuleDomain.DEV,
        supporting_claims=[SupportingClaim(claim_id=support_id)],
        confidence=0.8,
    )
    kernel.submit_candidate("pks", dependent)
    kernel.accept_candidate("pks", "I-MCP-DEPENDS")
    stored = kernel.load_claim("pks", "I-MCP-DEPENDS")
    stored.last_verified = date(2025, 1, 1)
    kernel.claims.claim_engine("pks").save_claim(stored)
    kernel.expire_claim("pks", support_id)

    issues = get_reverification_issues(kernel, "pks")
    verified = verify_claim(kernel, token["token"], "pks", "I-MCP-DEPENDS")

    assert issues[0]["claim_id"] == "I-MCP-DEPENDS"
    assert issues[0]["reason"] == "support_chain_broken"
    assert verified["claim_id"] == "I-MCP-DEPENDS"
    assert get_reverification_issues(kernel, "pks") == []
