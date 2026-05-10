from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CapsuleDomain(StrEnum):
    CONTENT = "content"
    DEV = "dev"
    RESEARCH = "research"


class Relation(StrEnum):
    SUPPORTS = "supports"
    WEAK_SUPPORTS = "weak_supports"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"


class EvidenceSourceType(StrEnum):
    FILE = "file"
    URL = "url"
    MANUAL = "manual"
    COMMAND = "command"
    CONVERSATION = "conversation"
    KERNEL_EVENT = "kernel_event"


class ClaimType(StrEnum):
    FACTUAL = "factual"
    INFERENCE = "inference"
    PREFERENCE = "preference"
    CONSTRAINT = "constraint"


class ClaimStatus(StrEnum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    DISPUTED = "disputed"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class ReviewAction(StrEnum):
    AUTO_ACCEPT = "auto_accept"
    MANUAL_REVIEW = "manual_review"
    REJECT = "reject"


class Qualifier(BaseModel):
    scope: str | None = None
    condition: str | None = None
    temporal: str | None = None

    def is_empty(self) -> bool:
        return not (self.scope or self.condition or self.temporal)


class Evidence(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    source_ref: str
    source_type: EvidenceSourceType | None = None
    relation: Relation
    excerpt: str
    locator: str | None = None

    @field_validator("source_ref", "excerpt")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("evidence source_ref and excerpt must not be empty")
        return value

    @model_validator(mode="after")
    def infer_source_type(self) -> Evidence:
        if self.source_type is None:
            source_ref = self.source_ref.strip()
            if source_ref == "manual":
                self.source_type = EvidenceSourceType.MANUAL.value
            elif source_ref.startswith("kernel_event:"):
                self.source_type = EvidenceSourceType.KERNEL_EVENT.value
            elif "://" in source_ref:
                self.source_type = EvidenceSourceType.URL.value
            else:
                self.source_type = EvidenceSourceType.FILE.value
        return self

    @property
    def source_type_value(self) -> str:
        if isinstance(self.source_type, StrEnum):
            return self.source_type.value
        return str(self.source_type)


class SupportingClaim(BaseModel):
    claim_id: str
    relation: Relation = Relation.SUPPORTS
    note: str | None = None

    @field_validator("claim_id")
    @classmethod
    def require_claim_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("supporting claim_id must not be empty")
        return value


class MinSupportRule(BaseModel):
    evidence: int = Field(default=0, ge=0)
    supporting_claims: int = Field(default=0, ge=0)
    evidence_or_claims_min: int = Field(default=0, ge=0)
    allowed_support_types: list[str] = Field(default_factory=list)
    requires_human_source: bool = False
    requires_manual_review: bool = False


class MinSupportStatus(BaseModel):
    passed: bool
    details: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    claim_id: str

    subject: str
    predicate: str
    object: str
    qualifier: str | None = None

    content: str = ""

    type: ClaimType = ClaimType.FACTUAL
    domain: CapsuleDomain
    tags: list[str] = Field(default_factory=list)

    supporting_claims: list[SupportingClaim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    status: ClaimStatus = ClaimStatus.CANDIDATE
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str = "human"
    valid_until: date | None = None
    last_verified: date | None = None

    supersedes: str | None = None
    superseded_by: str | None = None
    project: str = ""

    @field_validator("claim_id", "subject", "predicate", "object")
    @classmethod
    def require_core_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("claim core fields must not be empty")
        return value

    @field_validator("qualifier", mode="before")
    @classmethod
    def normalize_qualifier(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, dict):
            parts = [str(item).strip() for item in value.values() if str(item).strip()]
            return " · ".join(parts) or None
        text = str(value).strip()
        return text or None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        tags: list[str] = []
        for item in value:
            tag = item.strip()
            if tag and tag not in seen:
                seen.add(tag)
                tags.append(tag)
        return tags

    @model_validator(mode="after")
    def ensure_support_and_content(self) -> Claim:
        if not self.evidence and not self.supporting_claims:
            raise ValueError("claim requires evidence or supporting_claims")
        if not self.content.strip():
            self.content = f"{self.subject} {self.predicate} {self.object}"
        return self

    @property
    def conflict_key(self) -> tuple[str, str]:
        return (self.subject, self.predicate)

    def is_context_eligible(self, today: date | None = None, stale: bool = False) -> bool:
        today = today or date.today()
        if stale:
            return False
        if self.status_value != ClaimStatus.ACCEPTED.value:
            return False
        if self.valid_until is not None and self.valid_until < today:
            return False
        if self.superseded_by:
            return False
        return True

    def display_content(self) -> str:
        if self.content.strip():
            return self.content.strip()
        return f"{self.subject} {self.predicate} {self.object}"

    @property
    def type_value(self) -> str:
        return self.type.value if isinstance(self.type, StrEnum) else str(self.type)

    @property
    def status_value(self) -> str:
        return self.status.value if isinstance(self.status, StrEnum) else str(self.status)

    @property
    def domain_value(self) -> str:
        return self.domain.value if isinstance(self.domain, StrEnum) else str(self.domain)


class TrackingConfig(BaseModel):
    project_path: Path | None = None
    git_remote: str | None = None
    watched_paths: list[str] = Field(default_factory=list)
    auto_watch_evidence: bool = True
    last_synced_commit: str | None = None

    @field_validator("watched_paths")
    @classmethod
    def normalize_watched_paths(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class LifecycleRule(BaseModel):
    stale_after_days: int | None = Field(default=None, ge=1)
    auto_accept_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class DomainPolicy(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    domain: CapsuleDomain
    lifecycle: dict[str, LifecycleRule] = Field(default_factory=dict)
    min_support: dict[str, MinSupportRule] = Field(default_factory=dict)
    manual_review_types: list[str] = Field(default_factory=list)

    @classmethod
    def default_for(cls, domain: CapsuleDomain | str) -> DomainPolicy:
        domain_value = domain.value if isinstance(domain, StrEnum) else str(domain)
        stale_defaults: dict[str, int | None] = {
            ClaimType.FACTUAL.value: 180 if domain_value == CapsuleDomain.DEV.value else 365,
            ClaimType.INFERENCE.value: 90 if domain_value == CapsuleDomain.DEV.value else 180,
            ClaimType.PREFERENCE.value: None,
            ClaimType.CONSTRAINT.value: None,
        }
        return cls(
            domain=domain_value,
            lifecycle={
                claim_type.value: LifecycleRule(
                    stale_after_days=stale_defaults[claim_type.value],
                    auto_accept_threshold=0.85
                    if claim_type == ClaimType.FACTUAL
                    else None,
                )
                for claim_type in ClaimType
            },
            manual_review_types=[
                ClaimType.INFERENCE.value,
                ClaimType.PREFERENCE.value,
                ClaimType.CONSTRAINT.value,
            ],
            min_support={
                ClaimType.FACTUAL.value: MinSupportRule(
                    evidence=1,
                    supporting_claims=0,
                    allowed_support_types=[],
                ),
                ClaimType.INFERENCE.value: MinSupportRule(
                    evidence=0,
                    supporting_claims=0,
                    evidence_or_claims_min=1,
                    allowed_support_types=[ClaimType.FACTUAL.value],
                ),
                ClaimType.PREFERENCE.value: MinSupportRule(
                    evidence=1,
                    supporting_claims=0,
                    evidence_or_claims_min=1,
                    allowed_support_types=[
                        ClaimType.FACTUAL.value,
                        ClaimType.INFERENCE.value,
                    ],
                    requires_human_source=True,
                ),
                ClaimType.CONSTRAINT.value: MinSupportRule(
                    evidence=1,
                    supporting_claims=1,
                    evidence_or_claims_min=2,
                    allowed_support_types=[
                        ClaimType.FACTUAL.value,
                        ClaimType.INFERENCE.value,
                        ClaimType.PREFERENCE.value,
                    ],
                    requires_manual_review=True,
                ),
            },
        )

    def lifecycle_for(self, claim_type: ClaimType | str) -> LifecycleRule:
        claim_type_value = claim_type.value if isinstance(claim_type, StrEnum) else str(claim_type)
        return self.lifecycle.get(claim_type_value, LifecycleRule())

    def min_support_for(self, claim_type: ClaimType | str) -> MinSupportRule:
        claim_type_value = claim_type.value if isinstance(claim_type, StrEnum) else str(claim_type)
        if claim_type_value in self.min_support:
            return self.min_support[claim_type_value]
        return DomainPolicy.default_for(self.domain).min_support[claim_type_value]


class ReviewDecision(BaseModel):
    action: ReviewAction
    reason: str
    conflicts: list[str] = Field(default_factory=list)
    evidence_issues: list[str] = Field(default_factory=list)
    min_support_status: MinSupportStatus = Field(
        default_factory=lambda: MinSupportStatus(passed=True)
    )
    policy_notes: list[str] = Field(default_factory=list)


class ProjectionFilters(BaseModel):
    domains: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    predicates: list[str] = Field(default_factory=list)


class ProjectionSpec(BaseModel):
    projection_id: str
    output_path: str
    title: str
    description: str | None = None
    include_status: list[str] = Field(default_factory=lambda: [ClaimStatus.ACCEPTED.value])
    exclude_stale: bool = True
    filters: ProjectionFilters = Field(default_factory=ProjectionFilters)
    order: list[str] = Field(default_factory=lambda: ["type", "created_at"])
    group_by: str | None = None
    template: str | None = None


class ProjectMetadata(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    project_id: str
    name: str
    capsule_type: str
    domain: CapsuleDomain
    stage: str = ""
    current_goal: str = ""
    deliverable: str = ""
    constraints: list[str] = Field(default_factory=list)
    external_project_path: Path | None = None
    repository_url: str | None = None
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)

    @field_validator("project_id", "name", "capsule_type")
    @classmethod
    def require_metadata_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("project metadata fields must not be empty")
        return value

    @field_validator("constraints")
    @classmethod
    def normalize_constraints(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @model_validator(mode="after")
    def sync_tracking_aliases(self) -> ProjectMetadata:
        if self.external_project_path and self.tracking.project_path is None:
            self.tracking.project_path = self.external_project_path
        if self.repository_url and self.tracking.git_remote is None:
            self.tracking.git_remote = self.repository_url
        return self

    @property
    def domain_value(self) -> str:
        return self.domain.value if isinstance(self.domain, StrEnum) else str(self.domain)

    def project_root(self) -> Path | None:
        return self.tracking.project_path or self.external_project_path


class CapsuleResolution(BaseModel):
    project: ProjectMetadata
    capsule_path: Path


class EvidenceIssue(BaseModel):
    claim_id: str
    source_ref: str
    reason: str


class ClaimHealth(BaseModel):
    claim_id: str
    stale: bool = False
    expired: bool = False
    evidence_issues: list[EvidenceIssue] = Field(default_factory=list)
    min_support_issues: list[str] = Field(default_factory=list)


class HealthReport(BaseModel):
    project_id: str
    total_claims: int = 0
    accepted: int = 0
    candidate: int = 0
    stale: int = 0
    expired: int = 0
    disputed: int = 0
    superseded: int = 0
    min_support_violations: int = 0
    evidence_issues: list[EvidenceIssue] = Field(default_factory=list)
    claims: list[ClaimHealth] = Field(default_factory=list)

    def as_summary(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "total_claims": self.total_claims,
            "accepted": self.accepted,
            "candidate": self.candidate,
            "stale": self.stale,
            "expired": self.expired,
            "disputed": self.disputed,
            "superseded": self.superseded,
            "min_support_violations": self.min_support_violations,
            "evidence_issue_count": len(self.evidence_issues),
        }


class SnapshotRecord(BaseModel):
    commit_id: str
    message: str
    created_at: datetime | None = None
    created: bool = True
