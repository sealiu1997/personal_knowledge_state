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
    ProjectionFilters,
    ProjectionSpec,
    ProjectMetadata,
    Relation,
    SupportingClaim,
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
    tags: list[str] | None = None,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        subject=subject,
        predicate=predicate,
        object=object_,
        domain=CapsuleDomain.DEV,
        type=ClaimType.FACTUAL,
        tags=tags or ["project"],
        confidence=confidence,
        evidence=[evidence(source_ref, excerpt)],
    )


def submit_and_accept(kernel: Kernel, candidate: Claim) -> Claim:
    kernel.submit_candidate("pks", candidate)
    return kernel.accept_candidate("pks", candidate.claim_id)


def test_kernel_creates_loads_and_lists_capsules(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    capsule_path = kernel.create_capsule(project(tmp_path))

    loaded = kernel.load_capsule("pks")
    updated = kernel.update_capsule("pks", repository_url="git@example.invalid:pks.git")
    resolved = kernel.resolve_capsule("pks")
    listed = kernel.list_capsules()

    assert loaded.name == "PKS"
    assert updated.repository_url == "git@example.invalid:pks.git"
    assert resolved.capsule_path == capsule_path
    assert listed[0].project_id == "pks"
    assert (capsule_path / "candidates").is_dir()
    assert (capsule_path / "projections" / "architecture.md").is_file()
    assert (kernel.home / "domains" / "dev" / "claim_policy.yaml").is_file()
    project_yaml = (capsule_path / "project.yaml").read_text(encoding="utf-8")
    assert "stage:" not in project_yaml


def test_kernel_recommends_auto_accept_but_keeps_candidate_separate(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))

    decision = kernel.submit_candidate("pks", claim("CLM-2026-0001"))
    candidates = kernel.list_candidates("pks")
    rendered_before_accept = kernel.render_context("pks")
    accepted = kernel.accept_candidate("pks", "CLM-2026-0001")
    rendered = kernel.render_context("pks")

    assert decision.action == "auto_accept"
    assert candidates[0].claim_id == "CLM-2026-0001"
    assert "independent PKS home" not in rendered_before_accept
    assert accepted.status_value == ClaimStatus.ACCEPTED.value
    assert kernel.list_candidates("pks") == []
    assert "independent PKS home" in rendered


def test_conflicting_accepted_claims_become_disputed(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    submit_and_accept(kernel, claim("CLM-2026-0001", object_="independent PKS home"))

    decision = kernel.submit_candidate("pks", claim("CLM-2026-0002", object_="project folder"))
    disputed = kernel.accept_candidate("pks", "CLM-2026-0002")
    statuses = {item.claim_id: item.status_value for item in kernel.list_claims("pks")}

    assert decision.action == "manual_review"
    assert decision.conflicts == ["CLM-2026-0001"]
    assert disputed.status_value == ClaimStatus.DISPUTED.value
    assert statuses["CLM-2026-0001"] == ClaimStatus.DISPUTED.value
    assert statuses["CLM-2026-0002"] == ClaimStatus.DISPUTED.value


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
    submit_and_accept(kernel, stale_claim)

    report = kernel.health_check("pks", today=date(2026, 5, 9))
    stale_result = kernel.mark_claim_stale("pks", "CLM-2026-0003")
    stored_claim = kernel.load_claim("pks", "CLM-2026-0003")
    rendered = kernel.render_context("pks")

    assert report.stale == 1
    assert stale_result.stale
    assert stored_claim.status_value == ClaimStatus.ACCEPTED.value
    assert "independent PKS home" not in rendered


def test_health_reports_evidence_integrity_issues(tmp_path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "design.md").write_text("Current architecture.", encoding="utf-8")
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path, project_root))

    submit_and_accept(kernel, claim("CLM-2026-0004", source_ref="design.md", excerpt="old text"))

    report = kernel.health_check("pks")

    assert report.stale == 1
    assert report.evidence_issues[0].reason == "excerpt not found in source"


def test_maintenance_enforces_expiry_idempotently_and_refreshes(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    expired_claim = claim("CLM-EXPIRY", object_="temporary state")
    expired_claim.valid_until = date(2026, 5, 1)
    submit_and_accept(kernel, expired_claim)

    report = kernel.maintenance.run_all("pks", today=date(2026, 5, 9))
    second_report = kernel.maintenance.run_all("pks", today=date(2026, 5, 9))
    stored_claim = kernel.load_claim("pks", "CLM-EXPIRY")
    audit_predicates = [
        audit_claim.predicate for audit_claim in kernel.list_claims("pks", tag="audit")
    ]

    assert report.expired_enforced == 1
    assert report.projections_refreshed
    assert second_report.expired_enforced == 0
    assert stored_claim.status_value == ClaimStatus.EXPIRED.value
    assert audit_predicates.count("was_expired_by") == 1


def test_maintenance_reports_stale_and_evidence_issues(tmp_path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "design.md").write_text("Current architecture.", encoding="utf-8")
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path, project_root))
    stale_claim = claim("CLM-STALE", source_ref="design.md", excerpt="old text")
    stale_claim.last_verified = date(2025, 1, 1)
    submit_and_accept(kernel, stale_claim)

    report = kernel.maintenance.run("pks", today=date(2026, 5, 9), expiry=False)

    assert report.stale_found == 1
    assert report.evidence_issues_found == 1


def test_p32_maintenance_flags_broken_support_and_verify_resolves(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    submit_and_accept(kernel, claim("F-SUPPORT"))
    dependent = Claim(
        claim_id="I-DEPENDS",
        subject="PKS inference",
        predicate="depends_on",
        object="supporting fact",
        type=ClaimType.INFERENCE,
        domain=CapsuleDomain.DEV,
        tags=["architecture"],
        supporting_claims=[SupportingClaim(claim_id="F-SUPPORT")],
        confidence=0.8,
    )
    submit_and_accept(kernel, dependent)
    dependent = kernel.load_claim("pks", "I-DEPENDS")
    dependent.last_verified = date(2026, 1, 1)
    kernel.claims.claim_engine("pks").save_claim(dependent)

    kernel.expire_claim("pks", "F-SUPPORT")
    report = kernel.maintenance.run("pks", today=date(2026, 5, 14), evidence=False)
    issue = report.reverification_issues[0]
    verified = kernel.verify_claim("pks", "I-DEPENDS", today=date(2026, 5, 14))
    resolved = kernel.health_check("pks", today=date(2026, 5, 14))
    audit_predicates = [
        audit_claim.predicate for audit_claim in kernel.list_claims("pks", tag="audit")
    ]

    assert report.reverification_needed == 1
    assert issue.claim_id == "I-DEPENDS"
    assert issue.reason == "support_chain_broken"
    assert issue.trigger_claim_id == "F-SUPPORT"
    assert kernel.load_claim("pks", "I-DEPENDS").status_value == ClaimStatus.ACCEPTED.value
    assert verified.last_verified == date(2026, 5, 14)
    assert resolved.reverification_needed == 0
    assert "was_verified_by" in audit_predicates


def test_p32_source_mutation_cascades_and_stops_at_verified_claims(tmp_path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    today = date.today()
    old_date = date(2026, 1, 1)
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
    kernel.sync_project("pks")

    source_claim = claim("F-SOURCE", source_ref="tracked.md", excerpt="v1")
    source_claim.last_verified = old_date
    submit_and_accept(kernel, source_claim)
    inference = Claim(
        claim_id="I-CASCADE",
        subject="PKS inference",
        predicate="depends_on",
        object="tracked source",
        type=ClaimType.INFERENCE,
        domain=CapsuleDomain.DEV,
        tags=["architecture"],
        supporting_claims=[SupportingClaim(claim_id="F-SOURCE")],
        confidence=0.8,
    )
    preference = Claim(
        claim_id="P-CASCADE",
        subject="PKS preference",
        predicate="depends_on",
        object="inference",
        type=ClaimType.PREFERENCE,
        domain=CapsuleDomain.DEV,
        tags=["architecture"],
        supporting_claims=[SupportingClaim(claim_id="I-CASCADE")],
        evidence=[evidence("manual", "用户手动设定")],
        confidence=0.8,
    )
    stop_claim = Claim(
        claim_id="P-STOP",
        subject="PKS stop",
        predicate="depends_on",
        object="inference",
        type=ClaimType.PREFERENCE,
        domain=CapsuleDomain.DEV,
        tags=["architecture"],
        supporting_claims=[SupportingClaim(claim_id="I-CASCADE")],
        evidence=[evidence("manual", "用户手动设定")],
        confidence=0.8,
    )
    submit_and_accept(kernel, inference)
    submit_and_accept(kernel, preference)
    submit_and_accept(kernel, stop_claim)
    for claim_id, verified_at in {
        "I-CASCADE": old_date,
        "P-CASCADE": old_date,
        "P-STOP": today,
    }.items():
        stored = kernel.load_claim("pks", claim_id)
        stored.last_verified = verified_at
        kernel.claims.claim_engine("pks").save_claim(stored)

    (project_root / "tracked.md").write_text("v2", encoding="utf-8")
    run_git(project_root, "add", "tracked.md")
    run_git(project_root, "commit", "-m", "update tracked")

    report = kernel.maintenance.run("pks", today=today, expiry=False)
    issues = {issue.claim_id: issue for issue in report.reverification_issues}
    kernel.verify_claim("pks", "F-SOURCE", today=today)
    resolved = kernel.health_check("pks", today=today)

    assert report.reverification_needed == 3
    assert issues["F-SOURCE"].reason == "evidence_source_changed"
    assert issues["F-SOURCE"].trigger_source == "tracked.md"
    assert issues["I-CASCADE"].reason == "cascade_dependency"
    assert issues["I-CASCADE"].trigger_claim_id == "F-SOURCE"
    assert issues["P-CASCADE"].reason == "cascade_dependency"
    assert issues["P-CASCADE"].trigger_claim_id == "I-CASCADE"
    assert "P-STOP" not in issues
    assert {issue.claim_id for issue in resolved.reverification_issues} == set()


def test_projection_can_be_written_without_being_source_of_truth(tmp_path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path, project_root))
    submit_and_accept(kernel, claim("CLM-2026-0005"))

    projection_path = kernel.render_projection("pks", write=True)

    assert projection_path == project_root / "PKS.md"
    assert "Generated from Claims" in projection_path.read_text(encoding="utf-8")


def test_claim_lifecycle_expire_dispute_and_supersede(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    submit_and_accept(kernel, claim("CLM-2026-0006", object_="YAML"))
    submit_and_accept(
        kernel,
        claim("CLM-2026-0007", predicate="has_projection", object_="PKS.md"),
    )
    new_claim = claim(
        "CLM-2026-0008",
        predicate="has_projection",
        object_="generated PKS.md",
    )

    expired = kernel.expire_claim("pks", "CLM-2026-0006")
    disputed = kernel.mark_claim_disputed("pks", "CLM-2026-0006")
    superseding = kernel.supersede_claim("pks", "CLM-2026-0007", new_claim)
    old_claim = kernel.load_claim("pks", "CLM-2026-0007")

    assert expired.status_value == ClaimStatus.EXPIRED.value
    assert disputed.status_value == ClaimStatus.DISPUTED.value
    assert superseding.status_value == ClaimStatus.ACCEPTED.value
    assert superseding.supersedes == "CLM-2026-0007"
    assert old_claim.status_value == ClaimStatus.SUPERSEDED.value
    assert old_claim.superseded_by == "CLM-2026-0008"
    audit_predicates = {
        audit_claim.predicate for audit_claim in kernel.list_claims("pks", tag="audit")
    }
    assert "was_expired_by" in audit_predicates
    assert "was_disputed_by" in audit_predicates
    assert "was_superseded_by" in audit_predicates


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


def test_type_level_taste_and_style_overrides_domain_level(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    domain_claim = claim("TS-DEV-001", subject="代码风格", predicate="prefers", object_="领域偏好")
    domain_claim.type = ClaimType.PREFERENCE.value
    domain_claim.status = ClaimStatus.ACCEPTED.value
    domain_claim.project = "domain:dev"
    type_claim = claim("TS-SOFT-001", subject="代码风格", predicate="prefers", object_="类型偏好")
    type_claim.type = ClaimType.PREFERENCE.value
    type_claim.status = ClaimStatus.ACCEPTED.value
    type_claim.project = "domain:dev:type:software"

    kernel.save_taste_claim(domain_claim)
    kernel.save_taste_claim(type_claim, capsule_type="SoftwareCapsule")

    rendered = kernel.render_context("pks")

    assert "TS-SOFT-001" in rendered
    assert "类型偏好" in rendered
    assert "领域偏好" not in rendered


def test_min_support_rejects_constraint_without_lower_claim_support(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    unsupported = claim("C-UNSUPPORTED", object_="Do not bypass review")
    unsupported.type = ClaimType.CONSTRAINT.value

    decision = kernel.submit_candidate("pks", unsupported)

    assert decision.action == "reject"
    assert not decision.min_support_status.passed
    assert kernel.list_candidates("pks") == []


def test_inference_can_be_supported_by_accepted_factual_claim(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    submit_and_accept(kernel, claim("F-SUPPORT", tags=["architecture"]))
    inference = Claim(
        claim_id="I-SUPPORTED",
        subject="PKS review",
        predicate="depends_on",
        object="accepted facts",
        type=ClaimType.INFERENCE,
        domain=CapsuleDomain.DEV,
        tags=["architecture"],
        supporting_claims=[SupportingClaim(claim_id="F-SUPPORT")],
        confidence=0.7,
    )

    decision = kernel.submit_candidate("pks", inference)

    assert decision.action == "manual_review"
    assert decision.min_support_status.passed
    assert kernel.load_candidate("pks", "I-SUPPORTED").supporting_claims[0].claim_id == "F-SUPPORT"


def test_reject_candidate_deletes_yaml_and_writes_audit_claim(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    capsule_path = kernel.create_capsule(project(tmp_path))
    kernel.submit_candidate("pks", claim("CLM-REJECT", object_="temporary idea"))

    audit_claim = kernel.reject_candidate("pks", "CLM-REJECT")

    assert not (capsule_path / "candidates" / "CLM-REJECT.yaml").exists()
    assert audit_claim.type_value == ClaimType.INFERENCE.value
    assert "audit" in audit_claim.tags
    assert "temporary idea" not in audit_claim.model_dump_json()


def test_projection_edit_apis_create_candidates_or_patch_directly(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))
    draft = claim("F-PROJ-1", object_="Projection edits go through Kernel", tags=[])

    decision = kernel.submit_projection_claim("pks", "project-summary", draft)
    accepted = kernel.accept_candidate("pks", "F-PROJ-1")
    patched = kernel.patch_projection_claim(
        "pks",
        "project-summary",
        "F-PROJ-1",
        {"content": "Projection edits are Kernel-mediated."},
    )
    semantic_decision = kernel.patch_projection_claim(
        "pks",
        "project-summary",
        "F-PROJ-1",
        {"object": "semantic edits require review"},
    )

    assert decision.action == "auto_accept"
    assert "project" in accepted.tags
    assert isinstance(patched, Claim)
    assert patched.content == "Projection edits are Kernel-mediated."
    assert isinstance(semantic_decision, object)
    assert len(kernel.list_candidates("pks")) == 1


def test_policy_validation_and_projection_listing(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))

    specs = kernel.list_projections("pks")
    issues = kernel.validate_policy("dev")

    assert [spec.projection_id for spec in specs] == [
        "project-summary",
        "journal",
        "dev-architecture",
        "dev-tasks",
    ]
    assert issues == []


def test_custom_projection_specs_are_persisted_and_editable(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    capsule_path = kernel.create_capsule(project(tmp_path))
    custom_spec = ProjectionSpec(
        projection_id="custom-notes",
        output_path="projections/custom_notes.md",
        title="Custom Notes",
        filters=ProjectionFilters(tags=["custom"]),
    )

    saved = kernel.create_projection_spec("pks", custom_spec)
    submit_and_accept(
        kernel,
        claim("F-CUSTOM-1", object_="Custom projection claim", tags=["custom"]),
    )
    rendered = kernel.render_projection("pks", projection_id="custom-notes", write=True)
    rendered_text = rendered.read_text(encoding="utf-8")
    updated = kernel.update_projection_spec("pks", "custom-notes", {"title": "Edited Notes"})
    kernel.delete_projection_spec("pks", "custom-notes")

    assert saved.projection_id == "custom-notes"
    assert (capsule_path / "projection_specs" / "custom-notes.yaml").exists() is False
    assert "Custom projection claim" in rendered_text
    assert updated.title == "Edited Notes"
    assert "custom-notes" not in [spec.projection_id for spec in kernel.list_projections("pks")]


def test_projection_integrity_detects_direct_markdown_edits(tmp_path) -> None:
    kernel = Kernel(tmp_path / "pks-home")
    capsule_path = kernel.create_capsule(project(tmp_path))

    assert kernel.check_projection_integrity("pks") == []
    projection_path = capsule_path / "projections" / "PKS_PROJECT.md"
    projection_path.write_text("manual edit", encoding="utf-8")
    issues = kernel.check_projection_integrity("pks")

    assert issues[0].projection_id == "project-summary"
    assert issues[0].reason == "projection modified outside Kernel"


def test_legacy_p0_capsule_migrates_runtime_fields_to_claims(tmp_path) -> None:
    home = tmp_path / "pks-home"
    capsule_path = home / "capsules" / "legacy"
    capsule_path.mkdir(parents=True)
    (capsule_path / "project.yaml").write_text(
        "\n".join(
            [
                "project_id: legacy",
                "name: Legacy",
                "capsule_type: SoftwareCapsule",
                "domain: dev",
                "stage: P0",
                "current_goal: Migrate me",
            ]
        ),
        encoding="utf-8",
    )

    kernel = Kernel(home)
    loaded = kernel.load_capsule("legacy")
    claims = kernel.list_claims("legacy", predicate="current_stage")
    project_yaml = (capsule_path / "project.yaml").read_text(encoding="utf-8")

    assert loaded.project_id == "legacy"
    assert (capsule_path / "candidates").is_dir()
    assert (capsule_path / "projections").is_dir()
    assert claims[0].object == "P0"
    assert "stage:" not in project_yaml


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
    updated_project = kernel.load_capsule("pks")

    assert first_sync["git_available"] is True
    assert updated_project.tracking.last_synced_commit == second_sync["current_commit"]
    assert second_sync["changed_paths"] == ["tracked.md"]


def test_explicit_snapshot_create_and_list_commits_pks_home(tmp_path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    kernel = Kernel(tmp_path / "pks-home")
    kernel.create_capsule(project(tmp_path))

    snapshot = kernel.create_snapshot("initial pks snapshot")
    snapshots = kernel.list_snapshots()
    unchanged = kernel.create_snapshot("no state changes")

    assert snapshot.created
    assert len(snapshot.commit_id) == 40
    assert snapshots[0].commit_id == snapshot.commit_id
    assert snapshots[0].message == "initial pks snapshot"
    assert unchanged.commit_id == snapshot.commit_id
    assert not unchanged.created


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
