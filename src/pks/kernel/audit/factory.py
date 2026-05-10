from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pks.kernel.claim.store import ClaimStore
from pks.models import (
    CapsuleDomain,
    Claim,
    ClaimStatus,
    ClaimType,
    Evidence,
    ProjectMetadata,
    Relation,
)


class AuditClaimFactory:
    def __init__(self, capsule_path: Path, next_claim_id: Callable[[ClaimType], str]) -> None:
        self.store = ClaimStore(capsule_path)
        self.next_claim_id = next_claim_id

    def record(
        self,
        project: ProjectMetadata,
        event: str,
        subject: str,
        predicate: str,
        object_: str,
        payload: dict[str, object] | None = None,
    ) -> Claim:
        payload = payload or {}
        timestamp = datetime.now(UTC).isoformat()
        payload_text = " ".join(
            f"{key}={value}" for key, value in sorted(payload.items()) if key != "body"
        ).strip()
        excerpt = f"event={event} {payload_text}".strip()
        claim = Claim(
            claim_id=self.next_claim_id(ClaimType.INFERENCE),
            subject=subject,
            predicate=predicate,
            object=object_,
            content=self._content(event, subject, object_),
            type=ClaimType.INFERENCE,
            domain=self._domain(project.domain),
            tags=["audit", event.split(".", 1)[0]],
            evidence=[
                Evidence(
                    source_ref=f"kernel_event:{event}",
                    source_type="kernel_event",
                    relation=Relation.SUPPORTS,
                    excerpt=excerpt,
                    locator=timestamp,
                )
            ],
            status=ClaimStatus.ACCEPTED,
            confidence=1.0,
            created_by="kernel",
            last_verified=datetime.now(UTC).date(),
            project=project.project_id,
        )
        self.store.save(claim)
        return claim

    def _content(self, event: str, subject: str, object_: str) -> str:
        return f"Kernel event `{event}` recorded for {subject}: {object_}."

    def _domain(self, domain: CapsuleDomain | str) -> CapsuleDomain | str:
        return domain.value if isinstance(domain, CapsuleDomain) else domain
