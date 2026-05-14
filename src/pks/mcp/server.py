from __future__ import annotations

from pathlib import Path
from typing import Any

from pks.kernel import Kernel
from pks.mcp.tools import read as read_tools
from pks.mcp.tools import write as write_tools


def create_server(home: Path | None = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        message = "Install the MCP optional dependency with `pip install .[mcp]`."
        raise RuntimeError(message) from exc

    kernel = Kernel(home)
    server = FastMCP("PKS")

    @server.tool()
    def get_project_context(project_id: str) -> str:
        return read_tools.get_project_context(kernel, project_id)

    @server.tool()
    def search_claims(
        project_id: str,
        status: str | None = None,
        type: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        subject: str | None = None,
        predicate: str | None = None,
        projection: str | None = None,
    ) -> list[dict[str, Any]]:
        return read_tools.search_claims(
            kernel,
            project_id,
            status=status,
            type=type,
            domain=domain,
            tag=tag,
            subject=subject,
            predicate=predicate,
            projection=projection,
        )

    @server.tool()
    def get_claim(project_id: str, claim_id: str) -> dict[str, Any]:
        return read_tools.get_claim(kernel, project_id, claim_id)

    @server.tool()
    def get_health(project_id: str) -> dict[str, Any]:
        return read_tools.get_health(kernel, project_id)

    @server.tool()
    def get_reverification_issues(project_id: str) -> list[dict[str, Any]]:
        return read_tools.get_reverification_issues(kernel, project_id)

    @server.tool()
    def list_projects() -> list[dict[str, Any]]:
        return read_tools.list_projects(kernel)

    @server.tool()
    def submit_candidate_claim(
        token: str,
        project_id: str,
        claim: dict[str, Any],
    ) -> dict[str, Any]:
        return write_tools.submit_candidate_claim(kernel, token, project_id, claim)

    @server.tool()
    def verify_claim(token: str, project_id: str, claim_id: str) -> dict[str, Any]:
        return write_tools.verify_claim(kernel, token, project_id, claim_id)

    return server


def run_server(home: Path | None = None, transport: str = "stdio") -> None:
    server = create_server(home)
    server.run(transport=transport)
