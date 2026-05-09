from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from pks.models import SnapshotRecord


class SnapshotManager:
    def __init__(self, home: Path) -> None:
        self.home = home

    def create_snapshot(self, message: str) -> SnapshotRecord:
        message = message.strip()
        if not message:
            raise ValueError("snapshot message must not be empty")

        self.home.mkdir(parents=True, exist_ok=True)
        self._ensure_repo()
        self._git("add", ".")

        if not self._has_staged_changes():
            current = self._latest_snapshot()
            if current is None:
                self._git("commit", "--allow-empty", "-m", message)
                return self._latest_snapshot(created=True)
            return current.model_copy(update={"created": False})

        self._git("commit", "-m", message)
        return self._latest_snapshot(created=True)

    def list_snapshots(self) -> list[SnapshotRecord]:
        if not (self.home / ".git").exists():
            return []
        output = self._git("log", "--format=%H%x1f%aI%x1f%s", allow_failure=True)
        records: list[SnapshotRecord] = []
        for line in output.splitlines():
            parts = line.split("\x1f", 2)
            if len(parts) != 3:
                continue
            commit_id, created_at, message = parts
            records.append(
                SnapshotRecord(
                    commit_id=commit_id,
                    created_at=datetime.fromisoformat(created_at),
                    message=message,
                )
            )
        return records

    def _ensure_repo(self) -> None:
        if not (self.home / ".git").exists():
            self._git("init")

    def _latest_snapshot(self, created: bool = False) -> SnapshotRecord | None:
        records = self.list_snapshots()
        if not records:
            return None
        return records[0].model_copy(update={"created": created})

    def _has_staged_changes(self) -> bool:
        completed = subprocess.run(
            self._git_command("diff", "--cached", "--quiet"),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return completed.returncode == 1

    def _git(self, *args: str, allow_failure: bool = False) -> str:
        completed = subprocess.run(
            self._git_command(*args),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 and not allow_failure:
            raise RuntimeError(completed.stderr.strip() or f"git command failed: {' '.join(args)}")
        return completed.stdout.strip()

    def _git_command(self, *args: str) -> list[str]:
        return [
            "git",
            "-C",
            str(self.home),
            "-c",
            "user.name=PKS Snapshot",
            "-c",
            "user.email=pks-snapshot@example.invalid",
            *args,
        ]
