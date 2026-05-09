import shutil
import subprocess
from datetime import date

import pytest

from pks.kernel import Kernel
from pks.models import (
    CapsuleDomain,
    Claim,
    ClaimStatus,
    ClaimType,
    Evidence,
    ProjectMetadata,
    Relation,
)


def project(tmp_path, project_path=None) -> ProjectMetadata:
    return ProjectMetadata(
        project_id="pks",
        name="PKS",
        capsule_type="SoftwareCapsule",
        domain=CapsuleDomain.DEV,
        stage="P0",
        current_goal="Create the P0 kernel slice.",
        external_project_path=project_path,
    )


def evidence(source_ref: str = "manual", excerpt: str = "用户手动设定") -> Evidence:
    return Evidence(source_ref=source_ref, relation=Relation.SUPPORTS, excerpt=excerpt)


def claim(
    claim_id: str,
    subject: str = "PKS",
    predicate: str = "stores_state_in",
    object_: str = "independent PKS home",
    confidence: float = 0.9,
    source_ref: str = "manual",
    excerpt: str = "用户手动设定",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        subject=subject,
        predicate=predicate,
        object=object_,
        domain=CapsuleDomain.DEV,
        type=ClaimType.FACTUAL,
        confidence=confidence,
        evidence=[evidence(source_ref, excerpt)],
    )


def test_kernel_creates_loads_and_lists_capsules(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    capsule_path = kernel.create_capsule(project(tmp_path))

    loaded = kernel.load_capsule("pks")
    listed = kernel.list_capsules()

    assert loaded.name == "PKS"
    assert listed[0].project_id == "pks"
    assert (capsule_path / "architecture.md").is_file()
    assert (kernel.home / "domains" / "dev" / "claim_policy.yaml").is_file()


def test_kernel_auto_accepts_high_confidence_factual_claim(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))

    decision = kernel.submit_claim("pks", claim("CLM-2026-0001"))
    claims = kernel.list_claims("pks")
    rendered = kernel.render_context("pks")

    assert decision.action == "auto_accept"
    assert claims[0].status_value == ClaimStatus.ACCEPTED.value
    assert "independent PKS home" in rendered


def test_conflicting_accepted_claims_become_disputed(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    kernel.submit_claim("pks", claim("CLM-2026-0001", object_="independent PKS home"))

    decision = kernel.submit_claim("pks", claim("CLM-2026-0002", object_="project folder"))
    disputed = kernel.accept_claim("pks", "CLM-2026-0002")
    statuses = {item.claim_id: item.status_value for item in kernel.list_claims("pks")}

    assert decision.action == "manual_review"
    assert decision.conflicts == ["CLM-2026-0001"]
    assert disputed.status_value == ClaimStatus.DISPUTED.value
    assert statuses == {
        "CLM-2026-0001": ClaimStatus.DISPUTED.value,
        "CLM-2026-0002": ClaimStatus.DISPUTED.value,
    }


def test_health_marks_stale_claims_and_context_excludes_them(tmp_path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "design.md").write_text("PKS state lives outside projects.", encoding="utf-8")
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path, project_root))

    stale_claim = claim(
        "CLM-2026-0003",
        source_ref="design.md",
        excerpt="PKS state lives outside projects.",
    )
    stale_claim.last_verified = date(2025, 1, 1)
    kernel.submit_claim("pks", stale_claim)

    report = kernel.health_check("pks", today=date(2026, 5, 9))
    rendered = kernel.render_context("pks")

    assert report.stale == 1
    assert "independent PKS home" not in rendered


def test_health_reports_evidence_integrity_issues(tmp_path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "design.md").write_text("Current architecture.", encoding="utf-8")
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path, project_root))

    kernel.submit_claim("pks", claim("CLM-2026-0004", source_ref="design.md", excerpt="old text"))

    report = kernel.health_check("pks")

    assert report.stale == 1
    assert report.evidence_issues[0].reason == "excerpt not found in source"


def test_projection_can_be_written_without_being_source_of_truth(tmp_path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path, project_root))
    kernel.submit_claim("pks", claim("CLM-2026-0005"))

    projection_path = kernel.render_projection("pks", write=True)

    assert projection_path == project_root / "PKS.md"
    assert "This file is generated from PKS Kernel state" in projection_path.read_text(
        encoding="utf-8"
    )


def test_context_injects_domain_taste_and_style_claims(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    taste_claim = claim(
        "TS-DEV-001",
        subject="代码风格",
        predicate="prefers",
        object_="函数式风格",
    )
    taste_claim.type = ClaimType.PREFERENCE.value
    taste_claim.status = ClaimStatus.ACCEPTED.value
    taste_claim.project = "domain:dev"
    kernel.registry.save_taste_claim(taste_claim)

    rendered = kernel.render_context("pks")

    assert "TS-DEV-001" in rendered
    assert "函数式风格" in rendered


def test_sync_project_reports_git_diff_for_watched_paths(tmp_path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "tracked.md").write_text("v1", encoding="utf-8")
    run_git(project_root, "init")
    run_git(project_root, "add", "tracked.md")
    run_git(project_root, "commit", "-m", "initial")

    kernel = Kernel(tmp_path / "pks-home")
    metadata = project(tmp_path, project_root)
    metadata.tracking.watched_paths = ["tracked.md"]
    kernel.create_capsule(metadata)

    first_sync = kernel.sync_project("pks")
    (project_root / "tracked.md").write_text("v2", encoding="utf-8")
    run_git(project_root, "add", "tracked.md")
    run_git(project_root, "commit", "-m", "update tracked")

    second_sync = kernel.sync_project("pks")

    assert first_sync["git_available"] is True
    assert second_sync["changed_paths"] == ["tracked.md"]


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
