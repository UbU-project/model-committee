import json
from pathlib import Path

from model_committee.cli import main
from model_committee.config import ModelCommitteeConfig
from model_committee.errors import ProviderError
from model_committee.orchestration import work_generate
from model_committee.providers.fake import _candidate_proposals_from_prompt
from model_committee.responses.schemas import WorkProposal


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
    assert manifest["schema_version"] == "0.3"
    assert "provider_attempts" in manifest
    assert "provider_successes" in manifest
    assert manifest["score_matrix"]
    assert manifest["cross_score_count"] >= 1
    assert manifest["quorum_result"]["valid"] is True
    assert manifest["artifact_publication_status"] == "operator_pending"
    for success in manifest["provider_successes"]:
        if success["response_path"]:
            assert Path(success["response_path"]).exists()
    for row in manifest["score_matrix"]:
        response_path = row["schema_validation"]["response_path"]
        if response_path:
            assert Path(response_path).exists()
    assert (run_dir / "patches" / "selected.patch").exists()
    commit_message = (run_dir / "commit_message.txt").read_text(encoding="utf-8")
    assert commit_message.startswith("UMC: ")
    assert (run_dir / "review.md").exists()
    review_text = (run_dir / "review.md").read_text(encoding="utf-8")
    assert "## Cross-Score Matrix" in review_text
    assert "## Disagreement Flags" in review_text
    assert "RUN_ID=" in review_text
    assert "git -C ../model-committee-artifacts commit -S" in review_text
    assert "git -C " in review_text
    assert " commit -S -F " in review_text


def test_secondary_provider_failure_is_logged_without_aborting(
    git_fixture_repo, tmp_path, monkeypatch
):
    class PassingCodexProvider:
        provider_id = "codex"

        def __init__(self, config, repo):
            self.config = config
            self.repo = repo

        def generate_work_proposal(self, run_dir, prompt_path, schema_path):
            del run_dir, prompt_path, schema_path
            return WorkProposal.model_validate_json(
                Path("tests/fixtures/fake_responses/codex_work_response.valid.json").read_text(
                    encoding="utf-8"
                )
            )

    class FailingOllamaProvider:
        provider_id = "ollama:failing"

        def __init__(self, ollama_config, model_config):
            del ollama_config
            self.model_config = model_config

        def generate_work_proposal(self, run_dir, prompt_path, schema_path):
            del run_dir, prompt_path, schema_path
            raise ProviderError(
                "ollama unavailable",
                timeout_seconds=17,
                response_path="runs/example/responses/ollama_failing_response.txt",
            )

    monkeypatch.setattr(work_generate, "CodexProvider", PassingCodexProvider)
    monkeypatch.setattr(work_generate, "OllamaWorkProvider", FailingOllamaProvider)

    config = ModelCommitteeConfig.model_validate(
        {
            "claude": {
                "enabled": False,
            },
            "ollama": {
                "models": [
                    {
                        "name": "failing",
                        "enabled": True,
                        "timeout_seconds": 17,
                    }
                ]
            },
        }
    )

    run_dir = work_generate.run_work_generate(
        git_fixture_repo,
        "UBU-Q0001",
        config,
        None,
        tmp_path / "runs",
        False,
        "test",
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "waiting_for_score"
    assert manifest["providers_succeeded"] == ["codex"]
    assert manifest["providers_failed"]
    failure = manifest["provider_failures"][0]
    assert failure["provider_id"] == "ollama:failing"
    assert failure["model_name"] == "failing"
    assert failure["phase"] == "work-generate"
    assert failure["failure_class"] == "ProviderError"
    assert failure["timeout_seconds"] == 17
    assert failure["quorum_met"] is True


def test_candidate_proposals_from_prompt_parses_score_prompt_format():
    proposals = [
        {"proposal_id": "codex-work-001", "provider_id": "codex"},
        {"proposal_id": "claude-work-001", "provider_id": "claude"},
    ]
    prompt = (
        "## Some header\n\nsome text\n\n"
        "## Candidate proposals\n\n"
        "```json\n" + json.dumps(proposals, indent=2) + "\n```\n\nmore text"
    )
    result = _candidate_proposals_from_prompt(prompt)
    assert result == proposals


def test_candidate_proposals_from_prompt_returns_empty_when_section_missing():
    assert _candidate_proposals_from_prompt("no candidate proposals section here") == []


def test_candidate_proposals_from_prompt_returns_empty_on_wrong_fence_label():
    prompt = "## Candidate proposals\n\n```python\n[]\n```"
    assert _candidate_proposals_from_prompt(prompt) == []
