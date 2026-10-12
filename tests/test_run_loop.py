from unittest.mock import Mock

import pytest

from model_committee.config import ModelCommitteeConfig
from model_committee.orchestration import run_loop


@pytest.mark.parametrize(
    ("worked_question_ids", "expected_question_id"),
    [
        (set(), "UBU-Q0001"),
        ({"UBU-Q0001"}, "UBU-Q0003"),
        ({"UBU-Q0001", "UBU-Q0003"}, "UBU-Q0001"),
        ({"UBU-Q0002"}, "UBU-Q0001"),
    ],
)
def test_run_loop_rotates_eligible_questions_before_generating(
    git_fixture_repo, tmp_path, monkeypatch, worked_question_ids, expected_question_id
):
    run_dir = tmp_path / "selected-run"
    generate = Mock(return_value=run_dir)
    score = Mock()
    select = Mock()
    monkeypatch.setattr(run_loop, "run_work_generate", generate)
    monkeypatch.setattr(run_loop, "run_work_score", score)
    monkeypatch.setattr(run_loop, "run_work_select", select)
    config = ModelCommitteeConfig()

    result = run_loop.run_loop(
        git_fixture_repo,
        config,
        None,
        tmp_path / "runs",
        True,
        phase_filter="Phase 1",
        worked_question_ids=worked_question_ids,
    )

    assert result == run_dir
    assert generate.call_args.args[1] == expected_question_id
    generate.assert_called_once()
    score.assert_called_once_with(run_dir, config, True)
    select.assert_called_once_with(run_dir)
