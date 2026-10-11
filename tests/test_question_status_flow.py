import difflib
import json
from pathlib import Path

import pytest

from model_committee.config import ModelCommitteeConfig
from model_committee.errors import HumanReviewRequired, PatchValidationError
from model_committee.orchestration.work_generate import run_work_generate
from model_committee.orchestration.work_score import run_work_score
from model_committee.orchestration.work_select import run_work_select
from model_committee.providers.fake import (
    FakeClaudeCodeProvider,
    FakeCodexProvider,
    FakeOllamaProvider,
)
from model_committee.responses.schemas import WorkProposal


@pytest.fixture()
def invalid_status_proposal(git_fixture_repo):
    original = (git_fixture_repo / "OPEN_QUESTIONS.md").read_text(encoding="utf-8")
    updated = original.replace("Status: Open", "Status: Resolved", 1)
    patch = "diff --git a/OPEN_QUESTIONS.md b/OPEN_QUESTIONS.md\n" + "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="a/OPEN_QUESTIONS.md",
            tofile="b/OPEN_QUESTIONS.md",
        )
    )
    proposal = WorkProposal.model_validate_json(
        Path("tests/fixtures/fake_responses/codex_work_response.valid.json").read_text(
            encoding="utf-8"
        )
    )
    return proposal.model_copy(
        update={
            "changed_files": ["OPEN_QUESTIONS.md"],
            "patch": patch,
            "questions_resolved": ["UBU-Q0001"],
        }
    )


def test_generation_fails_when_all_proposals_use_resolved_status(
    git_fixture_repo, tmp_path, monkeypatch, invalid_status_proposal
):
    def generate(self, *_args):
        return invalid_status_proposal.model_copy(
            update={"provider_id": self.provider_id, "proposal_id": f"{self.provider_id}-invalid"}
        )

    for provider in (FakeCodexProvider, FakeClaudeCodeProvider, FakeOllamaProvider):
        monkeypatch.setattr(provider, "generate_work_proposal", generate)
    runs_dir = tmp_path / "runs"
    with pytest.raises(PatchValidationError, match="no valid patch proposals"):
        run_work_generate(
            git_fixture_repo, "UBU-Q0001", ModelCommitteeConfig(), None, runs_dir, True, "test"
        )

    run_dir = next(runs_dir.iterdir())
    validations = json.loads((run_dir / "parsed" / "patch_validation_results.json").read_text())
    assert len(validations) == 3
    assert all(item["patch_applies"] and not item["question_schema_passed"] for item in validations)
    assert all("Invalid enum value for Status: Resolved" in item["error"] for item in validations)
    assert json.loads((run_dir / "manifest.json").read_text())["status"] == "failed"
    assert not (run_dir / "patches" / "selected.patch").exists()


def test_invalid_status_proposal_is_not_scored_or_selected(
    git_fixture_repo, tmp_path, monkeypatch, invalid_status_proposal
):
    monkeypatch.setattr(
        FakeCodexProvider, "generate_work_proposal", lambda *_args: invalid_status_proposal
    )
    config = ModelCommitteeConfig()
    run_dir = run_work_generate(
        git_fixture_repo, "UBU-Q0001", config, None, tmp_path / "runs", True, "test"
    )
    run_work_score(run_dir, config, True)
    run_work_select(run_dir)

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["automated_selection_valid"] is True
    assert manifest["selected_proposal_id"] != invalid_status_proposal.proposal_id
    assert all(
        row["proposal_id"] != invalid_status_proposal.proposal_id
        for row in manifest["score_matrix"]
    )
    assert "Status: Resolved" not in (run_dir / "patches" / "selected.patch").read_text()


@pytest.mark.parametrize("invalid_status", [False, True])
def test_selection_revalidates_legacy_results_and_cached_quorum(
    git_fixture_repo, tmp_path, invalid_status_proposal, invalid_status
):
    original = (git_fixture_repo / "OPEN_QUESTIONS.md").read_bytes()
    config = ModelCommitteeConfig()
    run_dir = run_work_generate(
        git_fixture_repo, "UBU-Q0001", config, None, tmp_path / "runs", True, "test"
    )
    run_work_score(run_dir, config, True)
    run_work_select(run_dir)
    assert (run_dir / "patches" / "selected.patch").exists()
    if invalid_status:
        for path in (run_dir / "parsed").glob("*_proposal.json"):
            proposal = json.loads(path.read_text())
            proposal.update(
                patch=invalid_status_proposal.patch,
                changed_files=invalid_status_proposal.changed_files,
                questions_resolved=invalid_status_proposal.questions_resolved,
            )
            path.write_text(json.dumps(proposal), encoding="utf-8")
    validation_path = run_dir / "parsed" / "patch_validation_results.json"
    legacy_validations = json.loads(validation_path.read_text())
    for item in legacy_validations:
        item.pop("question_schema_passed")
    validation_path.write_text(json.dumps(legacy_validations), encoding="utf-8")

    if invalid_status:
        with pytest.raises(HumanReviewRequired, match="no valid work proposal"):
            run_work_select(run_dir)
        assert not (run_dir / "patches" / "selected.patch").exists()
        assert not (run_dir / "commit_message.txt").exists()
        assert "Invalid enum value for Status: Resolved" in (run_dir / "review.md").read_text()
    else:
        run_work_select(run_dir)
        assert (run_dir / "patches" / "selected.patch").exists()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["automated_selection_valid"] is not invalid_status
    assert manifest["quorum_result"]["valid"] is not invalid_status
    assert all(
        item["question_schema_passed"] is not invalid_status
        for item in json.loads(validation_path.read_text())
    )
    assert (git_fixture_repo / "OPEN_QUESTIONS.md").read_bytes() == original
