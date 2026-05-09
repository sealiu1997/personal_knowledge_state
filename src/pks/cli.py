from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from pks import __version__
from pks.kernel import Kernel
from pks.models import (
    CapsuleDomain,
    Claim,
    ClaimType,
    Evidence,
    ProjectMetadata,
    Relation,
    TrackingConfig,
)

app = typer.Typer(
    help="PKS local-first knowledge state control plane.",
    invoke_without_command=True,
)
claim_app = typer.Typer(help="Manage evidence-backed Claims.")
project_app = typer.Typer(help="Manage Capsules and projections.")
snapshot_app = typer.Typer(help="Create and list explicit PKS home snapshots.")
app.add_typer(claim_app, name="claim")
app.add_typer(project_app, name="project")
app.add_typer(snapshot_app, name="snapshot")


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
    typer.echo(f"Evidence issues: {summary['evidence_issue_count']}")


@claim_app.command("add")
def claim_add(
    project_id: Annotated[str, typer.Argument(help="Project id.")],
    claim_id: Annotated[str, typer.Option(help="Stable Claim id.")],
    subject: Annotated[str, typer.Option(help="Claim subject.")],
    predicate: Annotated[str, typer.Option(help="Claim predicate.")],
    object_: Annotated[str, typer.Option("--object", help="Claim object.")],
    source_ref: Annotated[str, typer.Option(help="Evidence source reference.")],
    excerpt: Annotated[str, typer.Option(help="Evidence excerpt.")],
    claim_type: Annotated[
        ClaimType,
        typer.Option("--type", help="Claim type."),
    ] = ClaimType.FACTUAL,
    relation: Annotated[
        Relation,
        typer.Option(help="Evidence relation."),
    ] = Relation.SUPPORTS,
    confidence: Annotated[float, typer.Option(help="Confidence from 0.0 to 1.0.")] = 0.0,
    content: Annotated[str, typer.Option(help="Human-readable content.")] = "",
    created_by: Annotated[str, typer.Option(help="Creator id.")] = "human",
    tags: Annotated[str, typer.Option(help="Comma-separated tags.")] = "",
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
        confidence=confidence,
        created_by=created_by,
        evidence=[
            Evidence(
                source_ref=source_ref,
                relation=relation,
                excerpt=excerpt,
            )
        ],
    )
    decision = Kernel(home).submit_claim(project_id, claim)
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
    confidence: Annotated[float, typer.Option(help="Confidence from 0.0 to 1.0.")] = 0.0,
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
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    claims = Kernel(home).list_claims(project_id)
    if not claims:
        typer.echo("No claims.")
        return
    for claim in claims:
        typer.echo(f"{claim.claim_id}\t{claim.status_value}\t{claim.display_content()}")


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
    write: Annotated[
        bool,
        typer.Option("--write", help="Write PKS.md into project folder."),
    ] = False,
    home: Annotated[Path | None, typer.Option(help="Override PKS home path.")] = None,
) -> None:
    result = Kernel(home).render_projection(project_id, write=write)
    typer.echo(result)


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
