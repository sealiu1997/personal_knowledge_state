from pks.kernel.storage import read_yaml
from pks.models import CapsuleDomain, ProjectMetadata
from pks.storage import CapsuleStore


def test_store_initializes_independent_home(tmp_path) -> None:
    store = CapsuleStore(tmp_path / "pks-home")

    store.ensure_home()

    assert (store.home / "capsules").is_dir()
    assert (store.home / "domains" / "dev").is_dir()
    assert (store.home / "domains" / "content").is_dir()
    assert (store.home / "domains" / "research").is_dir()
    assert (store.home / "config.yaml").is_file()


def test_store_creates_minimal_capsule(tmp_path) -> None:
    store = CapsuleStore(tmp_path / "pks-home")
    project = ProjectMetadata(
        project_id="pks",
        name="PKS",
        capsule_type="SoftwareCapsule",
        domain=CapsuleDomain.DEV,
        stage="P0",
        current_goal="Create the P0 kernel slice.",
    )

    capsule_path = store.create_capsule(project)

    assert (capsule_path / "project.yaml").is_file()
    assert (capsule_path / "claims").is_dir()
    assert (capsule_path / "candidates").is_dir()
    assert (capsule_path / "projections").is_dir()
    assert (capsule_path / "projection_specs").is_dir()
    project_yaml = read_yaml(capsule_path / "project.yaml")
    assert "stage" not in project_yaml
    assert "current_goal" not in project_yaml
