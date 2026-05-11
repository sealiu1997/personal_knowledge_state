from __future__ import annotations

from pathlib import Path

from pks.kernel.capsule.layout import default_projection_specs
from pks.kernel.storage import read_yaml, write_yaml
from pks.models import ProjectionSpec


class ProjectionSpecManager:
    def __init__(self, capsules_dir: Path) -> None:
        self.capsules_dir = capsules_dir

    def list_projection_specs(self, project_id: str, capsule_type: str) -> list[ProjectionSpec]:
        specs = {spec.projection_id: spec for spec in default_projection_specs(capsule_type)}
        for custom_spec in self.list_custom_projection_specs(project_id):
            specs[custom_spec.projection_id] = custom_spec
        return list(specs.values())

    def list_custom_projection_specs(self, project_id: str) -> list[ProjectionSpec]:
        specs_dir = self.projection_specs_dir(project_id)
        if not specs_dir.exists():
            return []
        return [
            ProjectionSpec.model_validate(read_yaml(path))
            for path in sorted(specs_dir.glob("*.yaml"))
            if not path.name.startswith(".")
        ]

    def save_projection_spec(self, project_id: str, spec: ProjectionSpec) -> ProjectionSpec:
        self._validate_projection_spec(spec)
        write_yaml(
            self.projection_spec_path(project_id, spec.projection_id),
            spec.model_dump(mode="json", exclude_none=True),
        )
        return spec

    def load_custom_projection_spec(self, project_id: str, projection_id: str) -> ProjectionSpec:
        return ProjectionSpec.model_validate(
            read_yaml(self.projection_spec_path(project_id, projection_id))
        )

    def delete_projection_spec(self, project_id: str, projection_id: str) -> None:
        self.projection_spec_path(project_id, projection_id).unlink(missing_ok=False)

    def projection_specs_dir(self, project_id: str) -> Path:
        return self.capsules_dir / project_id / "projection_specs"

    def projection_spec_path(self, project_id: str, projection_id: str) -> Path:
        return self.projection_specs_dir(project_id) / f"{projection_id}.yaml"

    def load_projection_hashes(self, project_id: str) -> dict[str, str]:
        path = self.projection_hashes_path(project_id)
        if not path.exists():
            return {}
        data = read_yaml(path)
        return {str(key): str(value) for key, value in data.get("hashes", {}).items()}

    def save_projection_hashes(self, project_id: str, hashes: dict[str, str]) -> None:
        write_yaml(self.projection_hashes_path(project_id), {"hashes": hashes})

    def projection_hashes_path(self, project_id: str) -> Path:
        return self.projection_specs_dir(project_id) / ".projection_hashes.yaml"

    def _validate_projection_spec(self, spec: ProjectionSpec) -> None:
        if not spec.projection_id.strip():
            raise ValueError("projection_id must not be empty")
        output_path = Path(spec.output_path)
        if output_path.is_absolute():
            raise ValueError("projection output_path must be relative to capsule")
        if ".." in output_path.parts:
            raise ValueError("projection output_path must not contain '..'")
        if output_path.suffix != ".md":
            raise ValueError("projection output_path must end with .md")
