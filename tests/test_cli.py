import json

from model_committee import __version__
from model_committee.cli import main


def test_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == "model-committee 0.4.0"
    assert __version__ == "0.3.0"


def test_check_valid_repo(capsys):
    assert main(["check", "--repo", "tests/fixtures/valid_repo"]) == 0
    assert '"status": "passed"' in capsys.readouterr().out


def test_check_invalid_repo_exits_2():
    assert main(["check", "--repo", "tests/fixtures/invalid_nonexistent_dependency"]) == 2


def test_rank_consistency_failure_names_the_failure(capsys):
    assert main(["rank", "--repo", "tests/fixtures/invalid_priority_value"]) == 2
    err = capsys.readouterr().err
    assert "hard consistency failure:" in err
    assert "INVALID_ENUM_VALUE: UBU-Q9997: Invalid enum value for Priority: Urgent" in err
    assert "expected one of: MVP blocker, MVP important, Post-MVP, Research" in err


def test_rank_filters_phase_4(git_fixture_repo, capsys):
    questions_path = git_fixture_repo / "OPEN_QUESTIONS.md"
    text = questions_path.read_text(encoding="utf-8")
    questions_path.write_text(text.replace("Phase: Phase 1", "Phase: Phase 4", 1), encoding="utf-8")
    assert main(["rank", "--repo", str(git_fixture_repo)]) == 0
    unfiltered = json.loads(capsys.readouterr().out)
    assert {q["question_id"] for q in unfiltered["ranked_questions"]} == {"UBU-Q0001", "UBU-Q0003"}

    assert main(["rank", "--repo", str(git_fixture_repo), "--phase", "Phase 4"]) == 0
    filtered = json.loads(capsys.readouterr().out)
    assert filtered["phase_filter"] == "Phase 4"
    assert [q["question_id"] for q in filtered["ranked_questions"]] == ["UBU-Q0001"]
    assert filtered["selected_question_id"] == "UBU-Q0001"
