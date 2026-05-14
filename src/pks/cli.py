from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from pks import __version__
from pks.kernel import Kernel
from pks.mcp.auth import McpTokenManager
from pks.mcp.config import DEFAULT_TOKEN_PERMISSIONS
from pks.models import (
    CapsuleDomain,
    Claim,
    ClaimType,
    Evidence,
    EvidenceSourceType,
    ProjectionSpec,
    ProjectMetadata,
    Relation,
    SupportingClaim,
    TrackingConfig,
)

app = typer.Typer(
    help="PKS local-first knowledge state control plane.",
    invoke_without_command=True,
)
claim_app = typer.Typer(help="Manage evidence-backed Claims.")
project_app = typer.Typer(help="Manage Capsules and projections.")
review_app = typer.Typer(help="Review candidate Claims.")
policy_app = typer.Typer(help="Inspect and validate domain policies.")
snapshot_app = typer.Typer(help="Create and list explicit PKS home snapshots.")
mcp_app = typer.Typer(help="Run the PKS MCP server and manage MCP tokens.")
mcp_token_app = typer.Typer(help="Manage MCP write tokens.")
app.add_typer(claim_app, name="claim")
app.add_typer(project_app, name="project")
app.add_typer(review_app, name="review")
app.add_typer(policy_app, name="policy")
app.add_typer(snapshot_app, name="snapshot")
app.add_typer(mcp_app, name="mcp")
mcp_app.add_typer(mcp_token_app, name="token")


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show version and exit.", is_eager=True),
    ] = False,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command("init-home")
def init_home(
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    kernel = Kernel(home)
    kernel.init_home()
    typer.echo(f"Initialized PKS home at {kernel.home}")


@app.command("new")
def new_project(
    project_id: Annotated[str, typer.Argument(help="Stable project id.")],
    name: Annotated[str, typer.Option(help="Human-readable project name.")],
    capsule_type: Annotated[str, typer.Option(help="Capsule type, e.g. SoftwareCapsule.")],
    domain: Annotated[CapsuleDomain, typer.Option(help="Capsule domain.")],
    stage: Annotated[str, typer.Option(help="Current project stage.")],
    current_goal: Annotated[str, typer.Option(help="Current project goal.")] = "",
    deliverable: Annotated[str, typer.Option(help="Expected deliverable.")] = "",
    project_path: Annotated[
        Path | None,
        typer.Option("--project-path", help="External project folder tracked by this capsule."),
    ] = None,
    git_remote: Annotated[str | None, typer.Option("--git-remote", help="Git remote URL.")] = None,
    constraints: Annotated[
        str,
        typer.Option(help="Comma-separated constraints or prohibitions."),
    ] = "",
    watched_paths: Annotated[
        str,
        typer.Option("--watched-paths", help="Comma-separated files or globs to track."),
    ] = "",
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Skip interactive confirmation.")] = False,
) -> None:
    if not yes:
        typer.confirm(f"Create capsule `{project_id}`?", abort=True)

    project = ProjectMetadata(
        project_id=project_id,
        name=name,
        capsule_type=capsule_type,
        domain=domain,
        stage=stage,
        current_goal=current_goal,
        deliverable=deliverable,
        constraints=_split_csv(constraints),
        external_project_path=project_path,
        repository_url=git_remote,
        tracking=TrackingConfig(
            project_path=project_path,
            git_remote=git_remote,
            watched_paths=_split_csv(watched_paths),
        ),
    )
    capsule_path = Kernel(home).create_capsule(project)
    typer.echo(f"Created capsule at {capsule_path}")


@app.command("context")
def context(
    project_id: Annotated[str, typer.Argument(help="Project id to render.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    typer.echo(Kernel(home).render_context(project_id))


@app.command("health")
def health(
    project_id: Annotated[str, typer.Argument(help="Project id to check.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    report = Kernel(home).health_check(project_id)
    summary = report.as_summary()
    typer.echo(f"Project: {summary['project_id']}")
    typer.echo(f"Accepted: {summary['accepted']}")
    typer.echo(f"Candidate: {summary['candidate']}")
    typer.echo(f"Stale: {summary['stale']}")
    typer.echo(f"Expired: {summary['expired']}")
    typer.echo(f"Disputed: {summary['disputed']}")
    typer.echo(f"Superseded: {summary['superseded']}")
    typer.echo(f"Min support violations: {summary['min_support_violations']}")
    typer.echo(f"Evidence issues: {summary['evidence_issue_count']}")
    typer.echo(f"Re-verification needed: {summary['reverification_needed']}")


@app.command("maintain")
def maintain(
    project_id: Annotated[str | None, typer.Argument(help="Project id to maintain.")] = None,
    stale: Annotated[bool, typer.Option("--stale", help="Only run stale scan.")] = False,
    expiry: Annotated[bool, typer.Option("--expiry", help="Only enforce expiry.")] = False,
    evidence: Annotated[
        bool,
        typer.Option("--evidence", help="Only re-check evidence integrity."),
    ] = False,
    all_projects: Annotated[
        bool,
        typer.Option("--all", help="Run maintenance for all projects."),
    ] = False,
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    kernel = Kernel(home)
    if not all_projects and project_id is None:
        raise typer.BadParameter("provide a project_id or use --all")
    run_all_tasks = not (stale or expiry or evidence)
    selected = {
        "stale": stale or run_all_tasks,
        "expiry": expiry or run_all_tasks,
        "evidence": evidence or run_all_tasks,
    }
    project_ids = (
        [project.project_id for project in kernel.list_capsules()]
        if all_projects
        else [project_id]
    )
    for target_project_id in project_ids:
        if target_project_id is None:
            continue
        report = kernel.maintenance.run(target_project_id, **selected)
        _echo_maintenance_report(report)


@app.command("serve")
def serve(
    host: Annotated[str, typer.Option("--host", help="Host interface to bind.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Port to bind.")] = 8420,
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    import uvicorn

    from pks.web import create_app

    uvicorn.run(create_app(home), host=host, port=port)


@mcp_app.command("start")
def mcp_start(
    transport: Annotated[
        str,
        typer.Option("--transport", help="MCP transport: stdio or sse."),
    ] = "stdio",
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    from pks.mcp.server import run_server

    if transport not in {"stdio", "sse"}:
        raise typer.BadParameter("transport must be stdio or sse")
    try:
        run_server(home, transport=transport)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@mcp_token_app.command("create")
def mcp_token_create(
    label: Annotated[str, typer.Option("--label", help="Human-readable token label.")],
    permissions: Annotated[
        str,
        typer.Option("--permissions", help="Comma-separated permissions."),
    ] = ",".join(DEFAULT_TOKEN_PERMISSIONS),
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    token = McpTokenManager(home).create_token(label, _split_csv(permissions))
    typer.echo(f"Token ID: {token['token_id']}")
    typer.echo(f"Label: {token['label']}")
    typer.echo(f"Permissions: {','.join(token['permissions'])}")
    typer.echo(f"Token: {token['token']}")


@mcp_token_app.command("list")
def mcp_token_list(
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    tokens = McpTokenManager(home).list_tokens()
    if not tokens:
        typer.echo("No MCP tokens.")
        return
    for token in tokens:
        typer.echo(
            f"{token['token_id']}\t{','.join(token['permissions'])}\t"
            f"{token['label']}\t{token['created_at']}"
        )


@mcp_token_app.command("revoke")
def mcp_token_revoke(
    token_id: Annotated[str, typer.Argument(help="Token id to revoke.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    McpTokenManager(home).revoke_token(token_id)
    typer.echo(f"{token_id}: revoked")


@mcp_token_app.command("regenerate")
def mcp_token_regenerate(
    token_id: Annotated[str, typer.Argument(help="Token id to regenerate.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    token = McpTokenManager(home).regenerate_token(token_id)
    typer.echo(f"Token ID: {token['token_id']}")
    typer.echo(f"Label: {token['label']}")
    typer.echo(f"Permissions: {','.join(token['permissions'])}")
    typer.echo(f"Token: {token['token']}")


@claim_app.command("add")
def claim_add(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    claim_id: Annotated[str, typer.Option(help="Stable Claim id.")],
    subject: Annotated[str, typer.Option(help="Claim subject.")],
    predicate: Annotated[str, typer.Option(help="Claim predicate.")],
    object_: Annotated[str, typer.Option("--object", help="Claim object.")],
    source_ref: Annotated[str, typer.Option(help="Evidence source reference.")],
    excerpt: Annotated[str, typer.Option(help="Evidence excerpt.")],
    source_type: Annotated[
        EvidenceSourceType | None,
        typer.Option("--source-type", help="Evidence source type."),
    ] = None,
    locator: Annotated[str | None, typer.Option(help="Evidence locator.")] = None,
    claim_type: Annotated[
        ClaimType,
        typer.Option("--type", help="Claim type."),
    ] = ClaimType.FACTUAL,
    relation: Annotated[
        Relation,
        typer.Option(help="Evidence relation."),
    ] = Relation.SUPPORTS,
    confidence: Annotated[float, typer.Option(help="Confidence from 0.0 to 1.0.")] = 1.0,
    content: Annotated[str, typer.Option(help="Human-readable content.")] = "",
    created_by: Annotated[str, typer.Option(help="Creator id.")] = "human",
    tags: Annotated[str, typer.Option(help="Comma-separated tags.")] = "",
    supporting_claims: Annotated[
        str,
        typer.Option("--supporting-claims", help="Comma-separated accepted support Claim ids."),
    ] = "",
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    project = Kernel(home).load_capsule(project_id)
    claim = Claim(
        claim_id=claim_id,
        subject=subject,
        predicate=predicate,
        object=object_,
        content=content,
        type=claim_type,
        domain=project.domain,
        tags=_split_csv(tags),
        supporting_claims=[
            SupportingClaim(claim_id=claim_id) for claim_id in _split_csv(supporting_claims)
        ],
        confidence=confidence,
        created_by=created_by,
        evidence=[
            Evidence(
                source_ref=source_ref,
                source_type=source_type,
                relation=relation,
                excerpt=excerpt,
                locator=locator,
            )
        ],
    )
    decision = Kernel(home).submit_candidate(project_id, claim)
    typer.echo(f"{claim_id}: {decision.action} ({decision.reason})")


@claim_app.command("accept")
def claim_accept(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    claim_id: Annotated[str, typer.Argument(help="Claim id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    claim = Kernel(home).accept_claim(project_id, claim_id)
    typer.echo(f"{claim.claim_id}: {claim.status_value}")


@claim_app.command("expire")
def claim_expire(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    claim_id: Annotated[str, typer.Argument(help="Claim id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    claim = Kernel(home).expire_claim(project_id, claim_id)
    typer.echo(f"{claim.claim_id}: {claim.status_value}")


@claim_app.command("verify")
def claim_verify(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    claim_id: Annotated[str, typer.Argument(help="Claim id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    claim = Kernel(home).verify_claim(project_id, claim_id)
    typer.echo(f"{claim.claim_id}: verified {claim.last_verified}")


@claim_app.command("dispute")
def claim_dispute(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    claim_id: Annotated[str, typer.Argument(help="Claim id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    claim = Kernel(home).mark_claim_disputed(project_id, claim_id)
    typer.echo(f"{claim.claim_id}: {claim.status_value}")


@claim_app.command("supersede")
def claim_supersede(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    old_claim_id: Annotated[str, typer.Argument(help="Old Claim id.")],
    new_claim_id: Annotated[str, typer.Option("--claim-id", help="New Claim id.")],
    object_: Annotated[str, typer.Option("--object", help="New Claim object.")],
    source_ref: Annotated[str, typer.Option(help="Evidence source reference.")],
    excerpt: Annotated[str, typer.Option(help="Evidence excerpt.")],
    confidence: Annotated[float, typer.Option(help="Confidence from 0.0 to 1.0.")] = 1.0,
    content: Annotated[str, typer.Option(help="Human-readable content.")] = "",
    created_by: Annotated[str, typer.Option(help="Creator id.")] = "human",
    tags: Annotated[str, typer.Option(help="Comma-separated tags.")] = "",
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    kernel = Kernel(home)
    old_claim = kernel.load_claim(project_id, old_claim_id)
    new_claim = Claim(
        claim_id=new_claim_id,
        subject=old_claim.subject,
        predicate=old_claim.predicate,
        object=object_,
        content=content,
        type=old_claim.type,
        domain=old_claim.domain,
        tags=_split_csv(tags) or old_claim.tags,
        confidence=confidence,
        created_by=created_by,
        evidence=[
            Evidence(
                source_ref=source_ref,
                relation=Relation.SUPERSEDES,
                excerpt=excerpt,
            )
        ],
    )
    claim = kernel.supersede_claim(project_id, old_claim_id, new_claim)
    typer.echo(f"{old_claim_id} -> {claim.claim_id}: {claim.status_value}")


@claim_app.command("list")
def claim_list(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    status: Annotated[str | None, typer.Option("--status", help="Filter by Claim status.")] = None,
    claim_type: Annotated[str | None, typer.Option("--type", help="Filter by Claim type.")] = None,
    domain: Annotated[str | None, typer.Option("--domain", help="Filter by domain.")] = None,
    tag: Annotated[str | None, typer.Option("--tag", help="Filter by tag.")] = None,
    subject: Annotated[str | None, typer.Option("--subject", help="Filter by subject.")] = None,
    predicate: Annotated[
        str | None,
        typer.Option("--predicate", help="Filter by predicate."),
    ] = None,
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    claims = Kernel(home).list_claims(
        project_id,
        status=status,
        type=claim_type,
        domain=domain,
        tag=tag,
        subject=subject,
        predicate=predicate,
    )
    if not claims:
        typer.echo("No claims.")
        return
    for claim in claims:
        typer.echo(f"{claim.claim_id}\t{claim.status_value}\t{claim.display_content()}")


@review_app.command("list")
def review_list(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    candidates = Kernel(home).list_candidates(project_id)
    if not candidates:
        typer.echo("No candidates.")
        return
    for candidate in candidates:
        typer.echo(f"{candidate.claim_id}\t{candidate.type_value}\t{candidate.display_content()}")


@review_app.command("show")
def review_show(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    candidate_id: Annotated[str, typer.Argument(help="Candidate Claim id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    kernel = Kernel(home)
    candidate = kernel.load_candidate(project_id, candidate_id)
    decision = kernel.review_candidate(project_id, candidate_id)
    typer.echo(f"Claim: {candidate.claim_id}")
    typer.echo(f"Type: {candidate.type_value}")
    typer.echo(f"Content: {candidate.display_content()}")
    typer.echo(f"Recommendation: {decision.action} ({decision.reason})")
    typer.echo(f"Min support: {decision.min_support_status.passed}")
    for detail in decision.min_support_status.details:
        typer.echo(f"- {detail}")


@review_app.command("accept")
def review_accept(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    candidate_id: Annotated[str, typer.Argument(help="Candidate Claim id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    claim = Kernel(home).accept_candidate(project_id, candidate_id)
    typer.echo(f"{claim.claim_id}: {claim.status_value}")


@review_app.command("reject")
def review_reject(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    candidate_id: Annotated[str, typer.Argument(help="Candidate Claim id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    audit_claim = Kernel(home).reject_candidate(project_id, candidate_id)
    typer.echo(f"{candidate_id}: rejected ({audit_claim.claim_id})")


@policy_app.command("show")
def policy_show(
    domain: Annotated[str, typer.Argument(help="Domain id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    policy = Kernel(home).load_policy(domain)
    typer.echo(yaml.safe_dump(policy.model_dump(mode="json"), allow_unicode=True, sort_keys=False))


@policy_app.command("validate")
def policy_validate(
    domain: Annotated[str, typer.Argument(help="Domain id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    issues = Kernel(home).validate_policy(domain)
    if not issues:
        typer.echo("Policy valid.")
        return
    for issue in issues:
        typer.echo(f"- {issue}")
    raise typer.Exit(code=1)


@project_app.command("list")
def project_list(
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    projects = Kernel(home).list_capsules()
    if not projects:
        typer.echo("No capsules.")
        return
    for project in projects:
        typer.echo(f"{project.project_id}\t{project.domain_value}\t{project.name}")


@project_app.command("sync")
def project_sync(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    result = Kernel(home).sync_project(project_id)
    typer.echo(f"Git available: {result['git_available']}")
    typer.echo(f"Current commit: {result['current_commit']}")
    changed_paths = result.get("changed_paths") or []
    typer.echo(f"Changed paths: {len(changed_paths)}")
    for path in changed_paths:
        typer.echo(f"- {path}")
    evidence_issues = result.get("evidence_issues") or []
    typer.echo(f"Evidence issues: {len(evidence_issues)}")


@project_app.command("projection")
def project_projection(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    projection_id: Annotated[
        str | None,
        typer.Option("--projection-id", help="Projection id to render."),
    ] = None,
    write: Annotated[
        bool,
        typer.Option("--write", help="Write projection files."),
    ] = False,
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    result = Kernel(home).render_projection(project_id, projection_id=projection_id, write=write)
    typer.echo(result)


@project_app.command("projection-check")
def project_projection_check(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    issues = Kernel(home).check_projection_integrity(project_id)
    if not issues:
        typer.echo("Projection files valid.")
        return
    for issue in issues:
        typer.echo(f"{issue.projection_id}\t{issue.output_path}\t{issue.reason}")
    raise typer.Exit(code=1)


@project_app.command("projection-spec-list")
def project_projection_spec_list(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    for spec in Kernel(home).list_projections(project_id):
        typer.echo(f"{spec.projection_id}\t{spec.output_path}\t{spec.title}")


@project_app.command("projection-spec-show")
def project_projection_spec_show(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    projection_id: Annotated[str, typer.Argument(help="Projection id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    spec = Kernel(home).load_projection_spec(project_id, projection_id)
    typer.echo(yaml.safe_dump(spec.model_dump(mode="json"), allow_unicode=True, sort_keys=False))


@project_app.command("projection-spec-save")
def project_projection_spec_save(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    spec_path: Annotated[Path, typer.Argument(help="YAML ProjectionSpec path.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    spec = ProjectionSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8")))
    saved = Kernel(home).create_projection_spec(project_id, spec)
    typer.echo(f"{saved.projection_id}\t{saved.output_path}")


@project_app.command("projection-spec-update")
def project_projection_spec_update(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    projection_id: Annotated[str, typer.Argument(help="Projection id.")],
    patch_path: Annotated[Path, typer.Argument(help="YAML patch with ProjectionSpec fields.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    changes = yaml.safe_load(patch_path.read_text(encoding="utf-8")) or {}
    changes.pop("projection_id", None)
    updated = Kernel(home).update_projection_spec(project_id, projection_id, changes)
    typer.echo(f"{updated.projection_id}\t{updated.output_path}\t{updated.title}")


@project_app.command("projection-spec-delete")
def project_projection_spec_delete(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    projection_id: Annotated[str, typer.Argument(help="Projection id.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    Kernel(home).delete_projection_spec(project_id, projection_id)
    typer.echo(f"{projection_id}: deleted")


@snapshot_app.command("create")
def snapshot_create(
    message: Annotated[str, typer.Option("--message", "-m", help="Snapshot message.")],
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    snapshot = Kernel(home).create_snapshot(message)
    created = "created" if snapshot.created else "unchanged"
    typer.echo(f"{snapshot.commit_id}\t{created}\t{snapshot.message}")


@snapshot_app.command("list")
def snapshot_list(
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    snapshots = Kernel(home).list_snapshots()
    if not snapshots:
        typer.echo("No snapshots.")
        return
    for snapshot in snapshots:
        created_at = snapshot.created_at.isoformat() if snapshot.created_at else ""
        typer.echo(f"{snapshot.commit_id}\t{created_at}\t{snapshot.message}")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _echo_maintenance_report(report) -> None:
    typer.echo(f"Project: {report.project_id}")
    typer.echo(f"Stale found: {report.stale_found}")
    typer.echo(f"Expired enforced: {report.expired_enforced}")
    typer.echo(f"Evidence issues: {report.evidence_issues_found}")
    typer.echo(f"Re-verification needed: {report.reverification_needed}")
    for issue in report.reverification_issues:
        trigger = issue.trigger_claim_id or issue.trigger_source or ""
        suffix = f" ({trigger})" if trigger else ""
        typer.echo(f"- {issue.claim_id}: {issue.reason}{suffix}")
    typer.echo(f"Projections refreshed: {report.projections_refreshed}")
