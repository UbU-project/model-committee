import json
import subprocess

from model_committee import cli
from model_committee.cli import main


def test_doctor_checks_claude_json_schema_support(tmp_path, monkeypatch, capsys):
    config = tmp_path / "models.json"
    config.write_text(
        json.dumps(
            {
                "claude": {"doctor_smoke_test": True},
                "ollama": {"models": []},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cli.shutil, "which", lambda command: f"/usr/bin/{command}")
    monkeypatch.setattr(cli, "check_ollama_reachable", lambda base_url: (True, "ok"))
    monkeypatch.setattr(cli, "list_ollama_models", lambda base_url: [])

    def fake_run(args, **kwargs):
        del kwargs
        if args[:2] == ["codex", "exec"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=("--skip-git-repo-check --cd --model --sandbox --output-schema --json -o"),
                stderr="",
            )
        if args == ["claude", "--version"]:
            return subprocess.CompletedProcess(args, 0, stdout="2.1.146 (Claude Code)\n")
        if args == ["claude", "--help"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="--bare --print --output-format --json-schema --tools --model --max-turns",
            )
        if args == ["claude", "--bare", "auth", "status", "--json"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps({"loggedIn": True, "authMethod": "apiKey"}),
                stderr="",
            )
        if args[:3] == ["claude", "--bare", "--print"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps({"structured_output": {"ok": True}}),
                stderr="",
            )
        raise AssertionError(args)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert (
        main(
            [
                "doctor",
                "--repo",
                "tests/fixtures/valid_repo",
                "--config",
                str(config),
                "--runs-dir",
                str(tmp_path / "runs"),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "OK claude version 2.1.146 (Claude Code)" in out
    assert "OK claude --json-schema support" in out
    assert "OK claude auth status" in out
    assert "OK claude schema-native smoke test" in out
