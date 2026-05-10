from datetime import date

import pytest
from pydantic import ValidationError

from pks.models import CapsuleDomain, Claim, ClaimStatus, Evidence, Relation, SupportingClaim


def evidence() -> Evidence:
    return Evidence(
        source_ref="docs/core-design/pks_product_plan_v2.md#5-claim-system",
        relation=Relation.SUPPORTS,
        excerpt="Claim 强制要求 source_ref 和 evidence",
    )


def test_claim_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        Claim(
            claim_id="CLM-2026-0001",
            subject="PKS",
            predicate="uses_unit",
            object="Claim",
            domain=CapsuleDomain.DEV,
            evidence=[],
        )


def test_claim_can_use_supporting_claim_without_external_evidence() -> None:
    claim = Claim(
        claim_id="I-2026-0001",
        subject="PKS",
        predicate="implies",
        object="review loop",
        domain=CapsuleDomain.DEV,
        supporting_claims=[SupportingClaim(claim_id="F-00001")],
    )

    assert claim.supporting_claims[0].claim_id == "F-00001"


def test_claim_conflict_key_uses_subject_and_predicate() -> None:
    claim = Claim(
        claim_id="CLM-2026-0002",
        subject="PKS MVP",
        predicate="uses_stack",
        object="Python + FastAPI + SQLite",
        domain=CapsuleDomain.DEV,
        evidence=[evidence()],
    )

    assert claim.conflict_key == ("PKS MVP", "uses_stack")


def test_only_accepted_claim_without_expiry_is_context_eligible() -> None:
    claim = Claim(
        claim_id="CLM-2026-0003",
        subject="Context Pack",
        predicate="is",
        object="dynamic projection",
        domain=CapsuleDomain.DEV,
        status=ClaimStatus.ACCEPTED,
        valid_until=date(2099, 1, 1),
        evidence=[evidence()],
    )

    assert claim.is_context_eligible(today=date(2026, 5, 8))
