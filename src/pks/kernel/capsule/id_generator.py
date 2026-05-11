from __future__ import annotations

from pathlib import Path

from pks.kernel.storage import read_yaml, write_yaml
from pks.models import ClaimType

TYPE_CODE: dict[str, str] = {
    ClaimType.FACTUAL.value: "F",
    ClaimType.INFERENCE.value: "I",
    ClaimType.PREFERENCE.value: "P",
    ClaimType.CONSTRAINT.value: "C",
}


class ClaimIdGenerator:
    def __init__(self, home: Path) -> None:
        self.home = home

    def ensure_config(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        config_path = self.home / "config.yaml"
        if not config_path.exists():
            write_yaml(config_path, {"version": 1, "capsules_dir": "capsules", "claim_sequence": 0})

    def next_claim_id(self, claim_type: ClaimType | str) -> str:
        self.ensure_config()
        claim_type_value = (
            claim_type.value if isinstance(claim_type, ClaimType) else str(claim_type)
        )
        config_path = self.home / "config.yaml"
        config = read_yaml(config_path)
        sequence = int(config.get("claim_sequence", 0)) + 1
        config["claim_sequence"] = sequence
        write_yaml(config_path, config)
        return f"{TYPE_CODE[claim_type_value]}-{sequence:05d}"
