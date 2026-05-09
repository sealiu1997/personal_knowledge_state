from pks.context import ContextEngine
from pks.models import CapsuleDomain, Claim, ClaimStatus, Evidence, ProjectMetadata, Relation


def evidence() -> Evidence:
    return Evidence(
        source_ref="docs/core-design/pks_product_plan_v2.md#9-context-pack",
        relation=Relation.SUPPORTS,
        excerpt="Context Pack 是 PKS 最直接的价值输出",
    )


def test_context_excludes_non_accepted_claims() -> None:
    project = ProjectMetadata(
        project_id="pks",
        name="PKS",
        capsule_type="SoftwareCapsule",
        domain=CapsuleDomain.DEV,
        stage="P0",
    )
    accepted = Claim(
        claim_id="CLM-2026-0004",
        subject="PKS",
        predicate="stores_state_in",
        object="independent PKS home",
        domain=CapsuleDomain.DEV,
        status=ClaimStatus.ACCEPTED,
        evidence=[evidence()],
    )
    candidate = Claim(
        claim_id="CLM-2026-0005",
        subject="PKS",
        predicate="stores_state_in",
        object="project folder",
        domain=CapsuleDomain.DEV,
        status=ClaimStatus.CANDIDATE,
        evidence=[evidence()],
    )

    rendered = ContextEngine().render_markdown(project, [accepted, candidate])

    assert "independent PKS home" in rendered
    assert "project folder" not in rendered
