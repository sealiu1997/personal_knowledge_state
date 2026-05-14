from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from pks.kernel import Kernel
from pks.models import (
    CapsuleDomain,
    Claim,
    ClaimType,
    Evidence,
    ProjectMetadata,
    Relation,
    SupportingClaim,
)
from pks.web import create_app


def project(project_path=None) -> ProjectMetadata:
    return ProjectMetadata(
        project_id="pks",
        name="PKS",
        capsule_type="SoftwareCapsule",
        domain=CapsuleDomain.DEV,
        stage="P2",
        external_project_path=project_path,
    )


def claim(claim_id: str, object_: str = "web review") -> Claim:
    return Claim(
        claim_id=claim_id,
        subject="PKS",
        predicate="supports",
        object=object_,
        type=ClaimType.FACTUAL,
        domain=CapsuleDomain.DEV,
        tags=["project"],
        confidence=0.9,
        evidence=[
            Evidence(
                source_ref="manual",
                relation=Relation.SUPPORTS,
                excerpt="用户手动设定",
            )
        ],
    )


def test_web_dashboard_and_project_api(tmp_path) -> None:
    home = tmp_path / "pks-home"
    Kernel(home).create_capsule(project())
    client = TestClient(create_app(home))

    dashboard = client.get("/")
    api_response = client.get("/api/projects")

    assert dashboard.status_code == 200
    assert "Project Dashboard" in dashboard.text
    assert api_response.status_code == 200
    assert api_response.json()[0]["project_id"] == "pks"


def test_web_candidate_api_accepts_claim(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    kernel.submit_candidate("pks", claim("F-WEB-1"))
    client = TestClient(create_app(home))

    detail = client.get("/api/projects/pks/candidates/F-WEB-1")
    accepted = client.post("/api/projects/pks/candidates/F-WEB-1/accept")
    claims = client.get("/api/projects/pks/claims", params={"status": "accepted"})

    assert detail.status_code == 200
    assert detail.json()["review"]["action"] == "auto_accept"
    assert accepted.status_code == 200
    assert any(item["claim_id"] == "F-WEB-1" for item in claims.json())


def test_web_claim_pages_and_maintenance_api(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    kernel.submit_candidate("pks", claim("F-WEB-EXPIRY", "temporary web state"))
    kernel.accept_candidate("pks", "F-WEB-EXPIRY")
    expired = kernel.load_claim("pks", "F-WEB-EXPIRY")
    expired.valid_until = date(2026, 5, 1)
    kernel.claims.claim_engine("pks").save_claim(expired)
    client = TestClient(create_app(home))

    page = client.get("/projects/pks/claims")
    report = client.post("/api/projects/pks/maintain", params={"stale": False, "evidence": False})

    assert page.status_code == 200
    assert "F-WEB-EXPIRY" in page.text
    assert report.status_code == 200
    assert report.json()["expired_enforced"] == 1


def test_web_p3_claim_create_batch_edit_tree_and_config(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    client = TestClient(create_app(home))

    created = client.post(
        "/api/projects/pks/claims",
        json={
            "subject": "PKS Web",
            "predicate": "creates",
            "object": "candidate claims",
            "type": "factual",
            "tags": ["project"],
            "evidence": [
                {
                    "source_ref": "manual",
                    "relation": "supports",
                    "excerpt": "web api test",
                }
            ],
        },
    )
    candidate_id = kernel.list_candidates("pks")[0].claim_id
    batch = client.post("/api/projects/pks/candidates/batch-accept", json={"ids": [candidate_id]})
    patched = client.post(
        f"/api/projects/pks/claims/{candidate_id}/patch",
        json={"changes": {"content": "PKS Web creates reviewable candidate claims."}},
    )
    tree = client.get(f"/api/projects/pks/claims/{candidate_id}/evidence-tree")
    config = client.get("/projects/pks/config")

    assert created.status_code == 201
    assert candidate_id.startswith("F-")
    assert batch.json()["accepted"] == [candidate_id]
    assert patched.json()["content"] == "PKS Web creates reviewable candidate claims."
    assert tree.json()["claim"]["claim_id"] == candidate_id
    assert config.status_code == 200
    assert "Domain Policy" in config.text


def test_web_p3_projection_filter_and_support_tree(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    base = claim("F-WEB-SUPPORT", "supporting base")
    kernel.submit_candidate("pks", base)
    kernel.accept_candidate("pks", "F-WEB-SUPPORT")
    inference = Claim(
        claim_id="I-WEB-SUPPORTED",
        subject="PKS Web",
        predicate="depends_on",
        object="accepted facts",
        type=ClaimType.INFERENCE,
        domain=CapsuleDomain.DEV,
        tags=["project"],
        confidence=0.7,
        supporting_claims=[SupportingClaim(claim_id="F-WEB-SUPPORT")],
    )
    kernel.submit_candidate("pks", inference)
    kernel.accept_candidate("pks", "I-WEB-SUPPORTED")
    client = TestClient(create_app(home))

    claims = client.get("/api/projects/pks/claims", params={"projection": "project-summary"})
    tree = client.get("/projects/pks/claims/I-WEB-SUPPORTED/evidence-tree")

    assert any(item["claim_id"] == "I-WEB-SUPPORTED" for item in claims.json())
    assert tree.status_code == 200
    assert "F-WEB-SUPPORT" in tree.text


def test_web_p32_reverification_queue_and_confirm_action(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    base = claim("F-WEB-REVERIFY", "supporting base")
    kernel.submit_candidate("pks", base)
    kernel.accept_candidate("pks", "F-WEB-REVERIFY")
    dependent = Claim(
        claim_id="I-WEB-REVERIFY",
        subject="PKS Web",
        predicate="depends_on",
        object="supporting base",
        type=ClaimType.INFERENCE,
        domain=CapsuleDomain.DEV,
        tags=["project"],
        supporting_claims=[SupportingClaim(claim_id="F-WEB-REVERIFY")],
        confidence=0.7,
    )
    kernel.submit_candidate("pks", dependent)
    kernel.accept_candidate("pks", "I-WEB-REVERIFY")
    dependent = kernel.load_claim("pks", "I-WEB-REVERIFY")
    dependent.last_verified = date(2026, 1, 1)
    kernel.claims.claim_engine("pks").save_claim(dependent)
    kernel.expire_claim("pks", "F-WEB-REVERIFY")
    client = TestClient(create_app(home))

    page = client.get("/projects/pks")
    verified = client.post("/api/projects/pks/claims/I-WEB-REVERIFY/verify")
    resolved = client.get("/projects/pks")

    assert page.status_code == 200
    assert "Needs Re-verification" in page.text
    assert "I-WEB-REVERIFY" in page.text
    assert "support_chain_broken" in page.text
    assert "/projects/pks/claims/I-WEB-REVERIFY/expire" in page.text
    assert verified.status_code == 200
    assert verified.json()["claim_id"] == "I-WEB-REVERIFY"
    assert "Needs Re-verification" not in resolved.text


def test_web_p3_mcp_token_api(tmp_path) -> None:
    home = tmp_path / "pks-home"
    Kernel(home).create_capsule(project())
    client = TestClient(create_app(home))

    created = client.post(
        "/api/mcp/tokens",
        json={"label": "Codex", "permissions": ["read", "write"]},
    )
    token_id = created.json()["token_id"]
    listed = client.get("/api/mcp/tokens")
    regenerated = client.post(f"/api/mcp/tokens/{token_id}/regenerate")
    deleted = client.delete(f"/api/mcp/tokens/{regenerated.json()['token_id']}")

    assert created.status_code == 200
    assert created.json()["token"].startswith("pks_")
    assert "token" not in listed.json()[0]
    assert regenerated.json()["token_id"] != token_id
    assert deleted.json()["revoked"] is True


def test_web_token_page_generates_write_tokens_only(tmp_path) -> None:
    home = tmp_path / "pks-home"
    Kernel(home).create_capsule(project())
    client = TestClient(create_app(home))

    page = client.get("/tokens")
    created = client.post("/tokens", data={"label": "Codex"})

    assert "read only" not in page.text
    assert "Generate Write Token" in page.text
    assert created.status_code == 200
    assert "write" in created.text
    assert "read, write" not in created.text


def test_web_claim_new_form_has_dynamic_min_support_and_multiple_evidence(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    client = TestClient(create_app(home))

    page = client.get("/projects/pks/claims/new")
    payload = urlencode(
        [
            ("type", "factual"),
            ("subject", "PKS Web"),
            ("predicate", "collects"),
            ("object", "multiple evidence items"),
            ("content", "PKS Web collects multiple evidence items."),
            ("tags", "project"),
            ("confidence", "0.9"),
            ("created_by", "human"),
            ("source_ref", "manual"),
            ("source_type", "manual"),
            ("relation", "supports"),
            ("excerpt", "first evidence"),
            ("locator", ""),
            ("source_ref", "docs/adapter/web/claim_creation.md"),
            ("source_type", "file"),
            ("relation", "supports"),
            ("excerpt", "Evidence 子表单"),
            ("locator", "claim creation design"),
        ]
    )
    created = client.post(
        "/projects/pks/claims/new",
        content=payload,
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    candidate = kernel.list_candidates("pks")[0]

    assert page.status_code == 200
    assert "support-summary" in page.text
    assert "add-evidence" in page.text
    assert "Needs total support" in page.text
    assert created.status_code == 303
    assert len(candidate.evidence) == 2
    assert candidate.evidence[1].source_ref == "docs/adapter/web/claim_creation.md"


def test_web_p31_projection_management_api_and_pages(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    base = claim("F-PROJECTION", "projection preview")
    base.tags = ["custom-preview"]
    kernel.submit_candidate("pks", base)
    kernel.accept_candidate("pks", "F-PROJECTION")
    client = TestClient(create_app(home))

    page = client.get("/projects/pks/projections")
    projections = client.get("/api/projects/pks/projections")
    new_page = client.get("/projects/pks/projections/new")
    new_preview = client.post(
        "/api/projects/pks/projections/preview",
        json={
            "projection_id": "preview-only",
            "output_path": "projections/preview_only.md",
            "title": "Preview Only",
            "include_status": ["accepted"],
            "exclude_stale": True,
            "filters": {"tags": ["custom-preview"]},
            "order": ["created_at"],
        },
    )
    preview = client.post(
        "/api/projects/pks/projections/project-summary/preview",
        json={
            "include_status": ["accepted"],
            "exclude_stale": True,
            "filters": {"tags": ["custom-preview"]},
            "order": ["created_at"],
        },
    )
    built_in_update = client.post(
        "/api/projects/pks/projections/project-summary",
        json={
            "title": "Project Summary Edited",
            "output_path": "projections/should_not_change.md",
            "filters": {"tags": ["custom-preview"]},
        },
    )
    duplicate = client.post(
        "/api/projects/pks/projections",
        json={
            "projection_id": "project-summary",
            "output_path": "projections/duplicate.md",
            "title": "Duplicate",
        },
    )
    created = client.post(
        "/api/projects/pks/projections",
        json={
            "projection_id": "custom-preview",
            "output_path": "projections/custom_preview.md",
            "title": "Custom Preview",
            "include_status": ["accepted"],
            "exclude_stale": True,
            "filters": {"tags": ["custom-preview"]},
            "order": ["created_at"],
        },
    )
    rendered = client.get("/api/projects/pks/projections/custom-preview/render")
    claims = client.get("/api/projects/pks/projections/custom-preview/claims")
    write = client.post("/api/projects/pks/projections/custom-preview/write")
    built_in_delete = client.delete("/api/projects/pks/projections/project-summary")
    deleted = client.delete("/api/projects/pks/projections/custom-preview")

    assert page.status_code == 200
    assert "project-summary" in page.text
    assert new_page.status_code == 200
    assert "/api/projects/pks/projections/preview" in new_page.text
    assert projections.json()[0]["claim_count"] >= 0
    assert new_preview.json()["claim_count"] == 1
    assert not (home / "capsules" / "pks" / "projection_specs" / "preview-only.yaml").exists()
    assert preview.json()["claim_count"] == 1
    assert "F-PROJECTION" in preview.json()["markdown"]
    assert built_in_update.json()["title"] == "Project Summary Edited"
    assert built_in_update.json()["output_path"] == "projections/PKS_PROJECT.md"
    assert duplicate.status_code == 422
    assert created.status_code == 200
    assert rendered.json()["markdown"].startswith("<!-- Generated from Claims")
    assert claims.json()[0]["claim_id"] == "F-PROJECTION"
    assert write.json()["path"].endswith("custom_preview.md")
    assert built_in_delete.status_code == 422
    assert deleted.json()["deleted"] is True


def test_web_p31_pks_md_preview_and_policy_update(tmp_path) -> None:
    home = tmp_path / "pks-home"
    kernel = Kernel(home)
    kernel.create_capsule(project())
    client = TestClient(create_app(home))
    policy = client.get("/api/projects/pks/policy").json()
    policy["manual_review_types"] = ["constraint"]

    pks_md = client.get("/projects/pks/pks-md")
    api_pks_md = client.get("/api/projects/pks/pks-md")
    updated = client.post("/api/projects/pks/policy", json=policy)

    assert pks_md.status_code == 200
    assert "PKS.md Preview" in pks_md.text
    assert "Generated from Claims" in api_pks_md.json()["markdown"]
    assert updated.json()["manual_review_types"] == ["constraint"]


def test_claim_routes_are_split_for_p31() -> None:
    routes_dir = Path("src/pks/web/routes")

    assert not (routes_dir / "claims.py").exists()
    assert (routes_dir / "claims_pages.py").exists()
    assert (routes_dir / "claims_api.py").exists()
    assert (routes_dir / "claims_helpers.py").exists()
