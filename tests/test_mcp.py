import pytest

from pks.kernel import Kernel
from pks.mcp.auth import McpTokenManager
from pks.mcp.tools.read import list_projects
from pks.mcp.tools.write import submit_candidate_claim
from pks.models import CapsuleDomain, ProjectMetadata, TokenPermission


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
