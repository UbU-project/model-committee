import json

from model_committee.cli import main


def test_fake_provider_golden_flow(git_fixture_repo, tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    assert (
        main(
            [
                "work-generate",
                "--repo",
                str(git_fixture_repo),
                "--question",
                "UBU-Q0001",
                "--runs-dir",
                str(runs_dir),
                "--fake-providers",
            ]
        )
        == 0
    )
    run_id = capsys.readouterr().out.strip()
    run_dir = runs_dir / run_id
    assert main(["work-score", "--run", str(run_dir), "--fake-providers"]) == 0
    assert main(["work-select", "--run", str(run_dir)]) == 0
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "selected"
    assert (run_dir / "patches" / "selected.patch").exists()
    commit_message = (run_dir / "commit_message.txt").read_text(encoding="utf-8")
    assert commit_message.startswith("UMC: ")
    assert (run_dir / "review.md").exists()
    review_text = (run_dir / "review.md").read_text(encoding="utf-8")
    assert "git -C " in review_text
    assert " commit -S -F " in review_text
