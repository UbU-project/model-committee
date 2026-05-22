import json
import subprocess

import pytest

from model_committee.config import ClaudeConfig
from model_committee.errors import ModelOutputError
from model_committee.providers import claude as claude_module
from model_committee.providers.claude import ClaudeCodeProvider, build_claude_argv
from model_committee.responses.schema_files import write_work_proposal_schema


def _valid_work_payload() -> dict:
    return {
        "proposal_id": "claude-work-001",
        "provider_id": "claude",
        "model_name": "claude:sonnet",
        "question_id": "UBU-Q0001",
        "base_commit": "unknown",
        "summary": "summary",
        "rationale": "rationale",
        "changed_files": ["DESIGN.md"],
        "patch": "diff --git a/DESIGN.md b/DESIGN.md\n",
        "commit_message": "message",
        "validation_notes": [],
        "new_questions_added": [],
        "questions_resolved": [],
        "decisions_added": [],
        "requires_human_review": False,
    }


def test_claude_provider_argv_construction():
    config = ClaudeConfig(command="claude", model="sonnet")
    argv = build_claude_argv(config, "prompt", '{"type":"object"}')
    assert argv == [
        "claude",
        "--bare",
        "--print",
        "prompt",
        "--output-format",
        "json",
        "--json-schema",
        '{"type":"object"}',
        "--tools",
        "",
        "--model",
        "sonnet",
        "--max-turns",
        "1",
    ]
    assert "--allowedTools" not in argv
    assert "--allowed-tools" not in argv


def test_claude_provider_parses_structured_output(monkeypatch, tmp_path):
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps({"structured_output": _valid_work_payload()}),
            stderr="",
        )

    monkeypatch.setattr(claude_module.subprocess, "run", fake_run)
    run_dir = tmp_path / "run"
    prompt = tmp_path / "prompt.md"
    schema = tmp_path / "schema.json"
    prompt.write_text("prompt", encoding="utf-8")
    write_work_proposal_schema(schema)

    provider = ClaudeCodeProvider(ClaudeConfig(model="sonnet"), tmp_path)
    proposal = provider.generate_work_proposal(run_dir, prompt, schema)

    assert proposal.proposal_id == "claude-work-001"
    assert "--json-schema" in seen["args"]
    assert seen["kwargs"]["cwd"] == tmp_path
    metadata = json.loads((run_dir / "responses" / "claude_work_attempt.json").read_text())
    assert metadata["provider_name"] == "claude"
    assert metadata["schema_validation"]["valid"] is True
    assert (run_dir / "responses" / "claude_work_structured_output.json").exists()


def test_claude_provider_schema_validation_failure(monkeypatch, tmp_path):
    bad_payload = _valid_work_payload()
    bad_payload.pop("proposal_id")

    def fake_run(args, **kwargs):
        del kwargs
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps({"structured_output": bad_payload}),
            stderr="",
        )

    monkeypatch.setattr(claude_module.subprocess, "run", fake_run)
    run_dir = tmp_path / "run"
    prompt = tmp_path / "prompt.md"
    schema = tmp_path / "schema.json"
    prompt.write_text("prompt", encoding="utf-8")
    write_work_proposal_schema(schema)

    provider = ClaudeCodeProvider(ClaudeConfig(model="sonnet"), tmp_path)
    with pytest.raises(ModelOutputError, match="failed schema validation"):
        provider.generate_work_proposal(run_dir, prompt, schema)

    metadata = json.loads((run_dir / "responses" / "claude_work_attempt.json").read_text())
    assert metadata["schema_validation"]["valid"] is False
    assert "proposal_id" in metadata["schema_validation"]["message"]
