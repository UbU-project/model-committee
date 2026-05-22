from model_committee.cli import main


def test_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == "model-committee 0.2.0"


def test_check_valid_repo(capsys):
    assert main(["check", "--repo", "tests/fixtures/valid_repo"]) == 0
    assert '"status": "passed"' in capsys.readouterr().out


def test_check_invalid_repo_exits_2():
    assert main(["check", "--repo", "tests/fixtures/invalid_nonexistent_dependency"]) == 2
