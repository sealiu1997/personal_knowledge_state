from __future__ import annotations

import subprocess
from pathlib import Path

from pks.models import Claim, EvidenceIssue, ProjectMetadata


class ProjectTracker:
    def check_evidence(self, project: ProjectMetadata, claims: list[Claim]) -> list[EvidenceIssue]:
        issues: list[EvidenceIssue] = []
        for claim in claims:
            for evidence in claim.evidence:
                issue = self._check_one(project, claim, evidence.source_ref, evidence.excerpt)
                if issue:
                    issues.append(issue)
        return issues

    def sync_project(self, project: ProjectMetadata, claims: list[Claim]) -> dict[str, object]:
        root = project.project_root()
        evidence_issues = self.check_evidence(project, claims)
        result: dict[str, object] = {
            "git_available": False,
            "current_commit": None,
            "changed_paths": [],
            "evidence_issues": [issue.model_dump(mode="json") for issue in evidence_issues],
        }
        if root is None:
            return result

        root = root.expanduser()
        if not (root / ".git").exists():
            return result

        current_commit = self._git(root, "rev-parse", "HEAD")
        if not current_commit:
            return result

        result["git_available"] = True
        result["current_commit"] = current_commit

        old_commit = project.tracking.last_synced_commit
        if old_commit and old_commit != current_commit:
            paths = project.tracking.watched_paths or ["."]
            changed = self._git(
                root,
                "diff",
                "--name-only",
                f"{old_commit}..{current_commit}",
                "--",
                *paths,
            )
            result["changed_paths"] = [line for line in changed.splitlines() if line.strip()]

        return result

    def _check_one(
        self,
        project: ProjectMetadata,
        claim: Claim,
        source_ref: str,
        excerpt: str,
    ) -> EvidenceIssue | None:
        path = self._source_path(project, source_ref)
        if path is None:
            return None
        if not path.exists():
            return EvidenceIssue(
                claim_id=claim.claim_id,
                source_ref=source_ref,
                reason="source file missing",
            )
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return EvidenceIssue(
                claim_id=claim.claim_id,
                source_ref=source_ref,
                reason="source file is not utf-8 text",
            )
        if excerpt not in content:
            return EvidenceIssue(
                claim_id=claim.claim_id,
                source_ref=source_ref,
                reason="excerpt not found in source",
            )
        return None

    def _source_path(self, project: ProjectMetadata, source_ref: str) -> Path | None:
        ref = source_ref.split("#", 1)[0].strip()
        if not ref or ref == "manual" or "://" in ref:
            return None

        path = Path(ref).expanduser()
        if path.is_absolute():
            return path

        root = project.project_root()
        if root is not None:
            return root.expanduser() / path
        return Path.cwd() / path

    def _git(self, root: Path, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()
