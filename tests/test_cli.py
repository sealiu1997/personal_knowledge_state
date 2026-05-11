import shutil
import subprocess
from datetime import date

import pytest
import yaml
from typer.testing import CliRunner

from pks.cli import app
from pks.kernel import Kernel

runner = CliRunner()


def test_cli_claim_lifecycle_and_snapshot_commands(tmp_path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    home = tmp_path / "pks-home"
    project_root = tmp_path / "project"
    project_root.mkdir()

    result = runner.invoke(
        app,
        [
            "new",
            "pks",
            "--name",
            "PKS",
            "--capsule-type",
            "SoftwareCapsule",
            "--domain",
            "dev",
            "--stage",
            "P0",
            "--project-path",
            str(project_root),
            "--home",
            str(home),
            "--yes",
        ],
    )
    assert result.exit_code == 0

    add_claim(home, "CLM-CLI-001", "stores_state_in", "YAML", accept=True)
    result = runner.invoke(app, ["claim", "expire", "pks", "CLM-CLI-001", "--home", str(home)])
    assert result.exit_code == 0
    assert "expired" in result.output

    add_claim(home, "CLM-CLI-002", "has_projection", "PKS.md", accept=True)
    result = runner.invoke(app, ["claim", "dispute", "pks", "CLM-CLI-002", "--home", str(home)])
    assert result.exit_code == 0
    assert "disputed" in result.output

    add_claim(home, "CLM-CLI-003", "uses_kernel", "facade", accept=True)
    result = runner.invoke(
        app,
        [
            "claim",
            "supersede",
            "pks",
            "CLM-CLI-003",
            "--claim-id",
            "CLM-CLI-004",
            "--object",
            "facade plus modules",
            "--source-ref",
            "manual",
            "--excerpt",
            "用户手动设定",
            "--confidence",
            "0.9",
            "--home",
            str(home),
        ],
    )
    assert result.exit_code == 0
    assert "CLM-CLI-003 -> CLM-CLI-004" in result.output

    result = runner.invoke(
        app,
        ["snapshot", "create", "--message", "cli snapshot", "--home", str(home)],
    )
    assert result.exit_code == 0
    assert "cli snapshot" in result.output

    result = runner.invoke(app, ["snapshot", "list", "--home", str(home)])
    assert result.exit_code == 0
    assert "cli snapshot" in result.output


def test_cli_review_policy_and_claim_filters(tmp_path) -> None:
    home = tmp_path / "pks-home"
    result = runner.invoke(
        app,
        [
            "new",
            "pks",
            "--name",
            "PKS",
            "--capsule-type",
            "SoftwareCapsule",
            "--domain",
            "dev",
            "--stage",
            "P1",
            "--home",
            str(home),
            "--yes",
        ],
    )
    assert result.exit_code == 0

    add_claim(home, "CLM-CLI-REVIEW", "uses_review", "candidate queue")

    result = runner.invoke(app, ["review", "list", "pks", "--home", str(home)])
    assert result.exit_code == 0
    assert "CLM-CLI-REVIEW" in result.output

    result = runner.invoke(app, ["review", "show", "pks", "CLM-CLI-REVIEW", "--home", str(home)])
    assert result.exit_code == 0
    assert "Recommendation: auto_accept" in result.output

    result = runner.invoke(app, ["review", "accept", "pks", "CLM-CLI-REVIEW", "--home", str(home)])
    assert result.exit_code == 0
    assert "accepted" in result.output

    result = runner.invoke(
        app,
        ["claim", "list", "pks", "--predicate", "uses_review", "--home", str(home)],
    )
    assert result.exit_code == 0
    assert "CLM-CLI-REVIEW" in result.output

    result = runner.invoke(app, ["policy", "show", "dev", "--home", str(home)])
    assert result.exit_code == 0
    assert "min_support" in result.output

    result = runner.invoke(app, ["policy", "validate", "dev", "--home", str(home)])
    assert result.exit_code == 0
    assert "Policy valid." in result.output


def test_cli_maintain_enforces_expiry(tmp_path) -> None:
    home = tmp_path / "pks-home"
    result = runner.invoke(
        app,
        [
            "new",
            "pks",
            "--name",
            "PKS",
            "--capsule-type",
            "SoftwareCapsule",
            "--domain",
            "dev",
            "--stage",
            "P2",
            "--home",
            str(home),
            "--yes",
        ],
    )
    assert result.exit_code == 0
    add_claim(home, "CLM-CLI-EXPIRY", "has_temporary_state", "yes", accept=True)
    kernel = Kernel(home)
    expired_claim = kernel.load_claim("pks", "CLM-CLI-EXPIRY")
    expired_claim.valid_until = date(2026, 5, 1)
    kernel.claims.claim_engine("pks").save_claim(expired_claim)

    result = runner.invoke(app, ["maintain", "pks", "--expiry", "--home", str(home)])

    assert result.exit_code == 0
    assert "Expired enforced: 1" in result.output
    assert kernel.load_claim("pks", "CLM-CLI-EXPIRY").status_value == "expired"


def test_cli_project_sync_reports_git_state(tmp_path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    home = tmp_path / "pks-home"
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "tracked.md").write_text("v1", encoding="utf-8")
    run_git(project_root, "init")
    run_git(project_root, "add", "tracked.md")
    run_git(project_root, "commit", "-m", "initial")

    result = runner.invoke(
        app,
        [
            "new",
            "pks",
            "--name",
            "PKS",
            "--capsule-type",
            "SoftwareCapsule",
            "--domain",
            "dev",
            "--stage",
            "P0",
            "--project-path",
            str(project_root),
            "--watched-paths",
            "tracked.md",
            "--home",
            str(home),
            "--yes",
        ],
    )
    assert result.exit_code == 0

    result = runner.invoke(app, ["project", "sync", "pks", "--home", str(home)])
    assert result.exit_code == 0
    assert "Git available: True" in result.output


def test_cli_mcp_token_lifecycle(tmp_path) -> None:
    home = tmp_path / "pks-home"
    result = runner.invoke(
        app,
        [
            "mcp",
            "token",
            "create",
            "--label",
            "Codex",
            "--permissions",
            "read,write",
            "--home",
            str(home),
        ],
    )
    assert result.exit_code == 0
    assert "Token: pks_" in result.output
    token_id = next(
        line.split(":", 1)[1].strip()
        for line in result.output.splitlines()
        if line.startswith("Token ID:")
    )

    result = runner.invoke(app, ["mcp", "token", "list", "--home", str(home)])
    assert result.exit_code == 0
    assert token_id in result.output
    assert "pks_" not in result.output

    result = runner.invoke(app, ["mcp", "token", "revoke", token_id, "--home", str(home)])
    assert result.exit_code == 0
    assert "revoked" in result.output


def test_cli_projection_spec_and_integrity_commands(tmp_path) -> None:
    home = tmp_path / "pks-home"
    spec_path = tmp_path / "custom-spec.yaml"
    patch_path = tmp_path / "custom-spec-patch.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "projection_id": "cli-custom",
                "output_path": "projections/cli_custom.md",
                "title": "CLI Custom",
                "include_status": ["accepted"],
                "exclude_stale": True,
                "filters": {"tags": ["cli-custom"]},
                "order": ["created_at"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    patch_path.write_text(yaml.safe_dump({"title": "CLI Custom Edited"}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "new",
            "pks",
            "--name",
            "PKS",
            "--capsule-type",
            "SoftwareCapsule",
            "--domain",
            "dev",
            "--stage",
            "P1",
            "--home",
            str(home),
            "--yes",
        ],
    )
    assert result.exit_code == 0

    result = runner.invoke(
        app,
        ["project", "projection-spec-save", "pks", str(spec_path), "--home", str(home)],
    )
    assert result.exit_code == 0
    assert "cli-custom" in result.output

    result = runner.invoke(
        app,
        ["project", "projection-spec-show", "pks", "cli-custom", "--home", str(home)],
    )
    assert result.exit_code == 0
    assert "CLI Custom" in result.output

    result = runner.invoke(
        app,
        [
            "project",
            "projection-spec-update",
            "pks",
            "cli-custom",
            str(patch_path),
            "--home",
            str(home),
        ],
    )
    assert result.exit_code == 0
    assert "CLI Custom Edited" in result.output

    result = runner.invoke(app, ["project", "projection-check", "pks", "--home", str(home)])
    assert result.exit_code == 0
    assert "Projection files valid." in result.output

    result = runner.invoke(
        app,
        ["project", "projection-spec-delete", "pks", "cli-custom", "--home", str(home)],
    )
    assert result.exit_code == 0
    assert "deleted" in result.output


def add_claim(home, claim_id: str, predicate: str, object_: str, accept: bool = False) -> None:
    result = runner.invoke(
        app,
        [
            "claim",
            "add",
            "pks",
            "--claim-id",
            claim_id,
            "--subject",
            "PKS",
            "--predicate",
            predicate,
            "--object",
            object_,
            "--source-ref",
            "manual",
            "--excerpt",
            "用户手动设定",
            "--confidence",
            "0.9",
            "--tags",
            "project",
            "--home",
            str(home),
        ],
    )
    assert result.exit_code == 0
    if accept:
        result = runner.invoke(app, ["review", "accept", "pks", claim_id, "--home", str(home)])
        assert result.exit_code == 0


def run_git(root, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=PKS Test",
            "-c",
            "user.email=pks-test@example.invalid",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
