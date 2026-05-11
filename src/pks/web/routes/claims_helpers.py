from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from fastapi import Request

from pks.kernel.render.projection import claim_matches_projection
from pks.models import Claim
from pks.web.routes.common import dump_model


async def claim_form_data(request: Request) -> dict[str, Any]:
    values = await form_values(request)
    return {
        "type": first_value(values, "type") or "factual",
        "subject": first_value(values, "subject"),
        "predicate": first_value(values, "predicate"),
        "object": first_value(values, "object"),
        "qualifier": first_value(values, "qualifier") or None,
        "content": first_value(values, "content"),
        "tags": first_value(values, "tags") or "",
        "confidence": float(first_value(values, "confidence") or 1.0),
        "created_by": first_value(values, "created_by") or "human",
        "evidence": evidence_from_form(values),
        "supporting_claims": supporting_claims_from_form(values),
    }


async def form_values(request: Request) -> dict[str, list[str]]:
    body = (await request.body()).decode("utf-8")
    return parse_qs(body, keep_blank_values=True)


def first_value(values: dict[str, list[str]], key: str) -> str:
    return (values.get(key) or [""])[0].strip()


def evidence_from_form(values: dict[str, list[str]]) -> list[dict[str, str]]:
    source_refs = values.get("source_ref", [])
    excerpts = values.get("excerpt", [])
    source_types = values.get("source_type", [])
    relations = values.get("relation", [])
    locators = values.get("locator", [])
    row_count = max(
        len(source_refs),
        len(excerpts),
        len(source_types),
        len(relations),
        len(locators),
        0,
    )
    evidence_items: list[dict[str, str]] = []
    for index in range(row_count):
        source_ref = list_value(source_refs, index).strip()
        excerpt = list_value(excerpts, index).strip()
        if not source_ref and not excerpt:
            continue
        evidence = {
            "source_ref": source_ref or "manual",
            "source_type": list_value(source_types, index).strip() or None,
            "relation": list_value(relations, index).strip() or "supports",
            "excerpt": excerpt or "Submitted from PKS Web UI",
            "locator": list_value(locators, index).strip() or None,
        }
        evidence_items.append(
            {key: value for key, value in evidence.items() if value is not None}
        )
    return evidence_items


def list_value(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return values[index]


def supporting_claims_from_form(values: dict[str, list[str]]) -> list[dict[str, str]]:
    ids = [item.strip() for item in values.get("supporting_claims", []) if item.strip()]
    ids.extend(
        item.strip()
        for item in (first_value(values, "supporting_claim_ids") or "").split(",")
        if item.strip()
    )
    return [{"claim_id": claim_id, "relation": "supports"} for claim_id in ids]


def patch_changes(values: dict[str, list[str]]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for key in ["subject", "predicate", "object", "qualifier", "content"]:
        if key in values:
            changes[key] = first_value(values, key) or None
    if "tags" in values:
        changes["tags"] = [
            item.strip() for item in first_value(values, "tags").split(",") if item.strip()
        ]
    return changes


def projection_for_claim(kernel, project_id: str, claim: Claim) -> str:
    stale_ids = kernel.health.stale_claim_ids_for(project_id, [claim])
    for spec in kernel.list_projections(project_id):
        if claim_matches_projection(claim, spec, stale_ids):
            return spec.projection_id
    projections = kernel.list_projections(project_id)
    if projections:
        return projections[0].projection_id
    raise KeyError(f"no projection available for {project_id}")


def evidence_tree(kernel, project_id: str, claim: Claim, seen: set[str] | None = None) -> dict:
    seen = seen or set()
    if claim.claim_id in seen:
        return {
            "claim": dump_model(claim),
            "evidence": [dump_model(evidence) for evidence in claim.evidence],
            "supports": [],
            "cycle": True,
        }
    seen.add(claim.claim_id)
    supports = []
    for support in claim.supporting_claims:
        try:
            support_claim = kernel.load_claim(project_id, support.claim_id)
        except FileNotFoundError:
            supports.append({"missing": support.claim_id, "relation": support.relation})
            continue
        supports.append(evidence_tree(kernel, project_id, support_claim, seen.copy()))
    return {
        "claim": dump_model(claim),
        "evidence": [dump_model(evidence) for evidence in claim.evidence],
        "supports": supports,
        "cycle": False,
    }
