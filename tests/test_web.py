from datetime import date

from fastapi.testclient import TestClient

from pks.kernel import Kernel
from pks.models import CapsuleDomain, Claim, ClaimType, Evidence, ProjectMetadata, Relation
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
