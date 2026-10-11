from model_committee.runs import layout
from model_committee.runs.manifest import load_manifest


def test_repeated_run_ids_allocate_unique_directories(git_fixture_repo, tmp_path, monkeypatch):
    run_id = "20261011T120000Z-UBU-Q0001"
    monkeypatch.setattr(layout, "make_run_id", lambda question_id: run_id)
    runs_root = tmp_path / "runs"
    first_dir, first_manifest = layout.create_run_dir(
        runs_root, git_fixture_repo, "UBU-Q0001", None, "first command"
    )
    first_snapshot = (first_dir / "snapshot" / "DESIGN.md").read_text(encoding="utf-8")
    first_manifest_text = (first_dir / "manifest.json").read_text(encoding="utf-8")
    artifact = first_dir / "patches" / "selected.patch"
    artifact.write_text("first patch", encoding="utf-8")
    (git_fixture_repo / "DESIGN.md").write_text("updated source", encoding="utf-8")

    second_dir, second_manifest = layout.create_run_dir(
        runs_root, git_fixture_repo, "UBU-Q0001", None, "second command"
    )

    assert first_dir == runs_root / run_id
    assert second_dir == runs_root / f"{run_id}-1"
    assert first_manifest.run_id == run_id
    assert second_manifest.run_id == f"{run_id}-1"
    assert load_manifest(first_dir).run_id == run_id
    assert load_manifest(second_dir).run_id == f"{run_id}-1"
    assert (first_dir / "manifest.json").read_text(encoding="utf-8") == first_manifest_text
    assert (first_dir / "snapshot" / "DESIGN.md").read_text(encoding="utf-8") == first_snapshot
    assert artifact.read_text(encoding="utf-8") == "first patch"
    assert not (second_dir / "patches" / "selected.patch").exists()
    assert (second_dir / "snapshot" / "DESIGN.md").read_text(encoding="utf-8") == "updated source"


def test_run_id_collision_with_file_preserves_existing_file(
    git_fixture_repo, tmp_path, monkeypatch
):
    run_id = "20261011T120000Z-UBU-Q0001"
    monkeypatch.setattr(layout, "make_run_id", lambda question_id: run_id)
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    existing_file = runs_root / run_id
    existing_file.write_text("existing file", encoding="utf-8")
    (runs_root / f"{run_id}-1").mkdir()

    run_dir, manifest = layout.create_run_dir(
        runs_root, git_fixture_repo, "UBU-Q0001", None, "test command"
    )

    assert run_dir == runs_root / f"{run_id}-2"
    assert manifest.run_id == f"{run_id}-2"
    assert load_manifest(run_dir).run_id == manifest.run_id
    assert existing_file.read_text(encoding="utf-8") == "existing file"
