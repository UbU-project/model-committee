import subprocess
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock

import pytest

from model_committee import cli
from model_committee.config import ModelCommitteeConfig
from model_committee.constants import EXIT_RUNTIME_ERROR, EXIT_USER_CANCELED
from model_committee.errors import PatchValidationError
from model_committee.orchestration import uber_loop


REAL_SUBPROCESS_RUN = subprocess.run


def git(repo: Path, *args: str) -> str:
    return REAL_SUBPROCESS_RUN(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@dataclass
class LoopWorkspace:
    committee: Path
    repo: Path
    artifacts: Path
    remote: Path
    runs_dir: Path


@pytest.fixture()
def loop_workspace(tmp_path: Path, monkeypatch) -> LoopWorkspace:
    workspace = tmp_path / "workspace with spaces"
    committee = workspace / "model committee"
    repo = workspace / "design repo"
    artifacts = workspace / "model-committee-artifacts"
    remote = workspace / "artifact remote.git"
    committee.mkdir(parents=True)
    for path in (repo, artifacts):
        path.mkdir()
        git(path, "init", "-b", "main")
        git(path, "config", "user.name", "Test")
        git(path, "config", "user.email", "test@example.com")
        (path / "README.md").write_text("Original notes\n", encoding="utf-8")
    (repo / "DESIGN.md").write_text("Initial design\n", encoding="utf-8")
    for path in (repo, artifacts):
        git(path, "add", ".")
        git(path, "-c", "commit.gpgsign=false", "commit", "-m", "Initial commit")
    remote.mkdir()
    git(remote, "init", "--bare", "-b", "main")
    git(artifacts, "remote", "add", "origin", str(remote))
    git(artifacts, "push", "-u", "origin", "main")
    monkeypatch.chdir(committee)
    return LoopWorkspace(committee, repo, artifacts, remote, Path("custom runs"))


def write_run(workspace: LoopWorkspace, run_id: str, before: str, after: str) -> Path:
    run_dir = workspace.runs_dir / run_id
    (run_dir / "patches").mkdir(parents=True)
    (run_dir / "raw").mkdir()
    (run_dir / "patches" / "selected.patch").write_text(
        "diff --git a/DESIGN.md b/DESIGN.md\n"
        "--- a/DESIGN.md\n"
        "+++ b/DESIGN.md\n"
        "@@ -1 +1 @@\n"
        f"-{before}\n+{after}\n",
        encoding="utf-8",
    )
    (run_dir / "commit_message.txt").write_text(f"Update design: {after}\n", encoding="utf-8")
    (run_dir / "review.md").write_text(f"Review for {run_id}\n", encoding="utf-8")
    (run_dir / "raw" / "response.json").write_text('{"result": "selected"}\n', encoding="utf-8")
    return run_dir


def git_operation(command: list[str], workspace: LoopWorkspace) -> str | None:
    repo = Path(command[2]).resolve()
    args = command[3:]
    if args[0] == "apply":
        return "apply"
    if args[0] in {"add", "commit"}:
        prefix = "design" if repo == workspace.repo else "artifact"
        return f"{prefix}-{args[0]}"
    if args[0] == "push":
        return "push"
    return None


def without_signing(command: list[str]) -> list[str]:
    if command[3] == "commit":
        assert "-S" in command, "uber-loop must request a signed commit"
        return ["--no-gpg-sign" if arg == "-S" else arg for arg in command]
    return command


def test_repeats_only_after_signed_commits_and_artifact_push(loop_workspace, monkeypatch):
    workspace = loop_workspace
    config = ModelCommitteeConfig()
    config_path = Path("config with spaces.json")
    changes = ["Initial design", "First design", "Second design"]
    runs = []
    commands = []
    calls = []
    for path in (workspace.repo, workspace.artifacts):
        (path / "README.md").write_text("Unrelated local work\n", encoding="utf-8")

    def run_loop(*args, **kwargs):
        calls.append((args, kwargs))
        cycle = len(calls) - 1
        if cycle:
            previous = runs[-1]
            # Inspect the remote, so a local artifact commit alone cannot pass.
            assert git(workspace.remote, "show", f"HEAD:runs/{previous.name}/review.md") == (
                f"Review for {previous.name}"
            )
            assert git(workspace.repo, "show", "HEAD:DESIGN.md") == changes[cycle]
        if cycle == 2:
            raise KeyboardInterrupt
        run_dir = write_run(workspace, f"run-{cycle + 1}", changes[cycle], changes[cycle + 1])
        runs.append(run_dir)
        return run_dir

    def run(command, **kwargs):
        commands.append(command)
        return REAL_SUBPROCESS_RUN(without_signing(command), **kwargs)

    monkeypatch.setattr(uber_loop, "run_loop", run_loop)
    monkeypatch.setattr(uber_loop.subprocess, "run", run)
    with pytest.raises(KeyboardInterrupt):
        uber_loop.run_uber_loop(
            workspace.repo, config, config_path, workspace.runs_dir, True, phase_filter="Phase 4"
        )

    assert (
        calls
        == [
            (
                (workspace.repo, config, config_path, workspace.runs_dir, True),
                {"phase_filter": "Phase 4"},
            )
        ]
        * 3
    )
    for run_dir in runs:
        source = run_dir.resolve()
        published = workspace.artifacts / "runs" / run_dir.name
        assert {path.relative_to(source) for path in source.rglob("*") if path.is_file()} == {
            path.relative_to(published) for path in published.rglob("*") if path.is_file()
        }
        for path in source.rglob("*"):
            if path.is_file():
                assert path.read_bytes() == (published / path.relative_to(source)).read_bytes()
    operations = [git_operation(command, workspace) for command in commands]
    assert [op for op in operations if op] == [
        "apply",
        "design-add",
        "design-commit",
        "artifact-add",
        "artifact-commit",
        "push",
    ] * 2
    design_adds = [
        command[3:] for command in commands if git_operation(command, workspace) == "design-add"
    ]
    assert design_adds == [["add", "--", "DESIGN.md"]] * 2
    design_commits = [
        command[3:] for command in commands if git_operation(command, workspace) == "design-commit"
    ]
    assert design_commits == [
        ["commit", "-S", "-F", str(run_dir.resolve() / "commit_message.txt")] for run_dir in runs
    ]
    for path in (workspace.repo, workspace.artifacts):
        assert git(path, "show", "HEAD:README.md") == "Original notes"
        assert git(path, "diff", "--cached", "--name-only") == ""
        assert git(path, "status", "--porcelain") == "M README.md"
    assert git(workspace.repo, "log", "-2", "--format=%s").splitlines() == [
        "Update design: Second design",
        "Update design: First design",
    ]
    assert git(workspace.remote, "log", "-2", "--format=%s").splitlines() == [
        "UMC artifact run-2",
        "UMC artifact run-1",
    ]


@pytest.mark.parametrize(
    "failed_step",
    ["apply", "design-add", "design-commit", "copy", "artifact-add", "artifact-commit", "push"],
)
def test_failure_stops_before_later_steps_or_another_run(loop_workspace, monkeypatch, failed_step):
    workspace = loop_workspace
    run_dir = write_run(workspace, "failed-run", "Initial design", "Updated design")
    generation = Mock(return_value=run_dir)
    monkeypatch.setattr(uber_loop, "run_loop", generation)
    operations = []
    real_copytree = uber_loop.shutil.copytree

    def run(command, **kwargs):
        operation = git_operation(command, workspace)
        if operation:
            operations.append(operation)
        if operation == failed_step:
            raise subprocess.CalledProcessError(1, command)
        return REAL_SUBPROCESS_RUN(without_signing(command), **kwargs)

    def copytree(source, destination, *args, **kwargs):
        # copytree calls itself for nested directories; count only the run root.
        if Path(source).resolve() == run_dir.resolve():
            operations.append("copy")
            if failed_step == "copy":
                raise OSError("Forced artifact copy failure")
        return real_copytree(source, destination, *args, **kwargs)

    monkeypatch.setattr(uber_loop.subprocess, "run", run)
    monkeypatch.setattr(uber_loop.shutil, "copytree", copytree)
    with pytest.raises((RuntimeError, OSError)):
        uber_loop.run_uber_loop(workspace.repo, ModelCommitteeConfig(), None, workspace.runs_dir)
    steps = [
        "apply",
        "design-add",
        "design-commit",
        "copy",
        "artifact-add",
        "artifact-commit",
        "push",
    ]
    assert operations == steps[: steps.index(failed_step) + 1]
    generation.assert_called_once()
    assert git(workspace.remote, "log", "--format=%s") == "Initial commit"


@pytest.mark.parametrize("staged_repo", ["repo", "artifacts"])
def test_existing_staged_changes_stop_before_generation(loop_workspace, monkeypatch, staged_repo):
    workspace = loop_workspace
    path = getattr(workspace, staged_repo)
    (path / "README.md").write_text("Already staged work\n", encoding="utf-8")
    git(path, "add", "README.md")
    generation = Mock()
    monkeypatch.setattr(uber_loop, "run_loop", generation)
    with pytest.raises(RuntimeError, match="staged changes"):
        uber_loop.run_uber_loop(workspace.repo, ModelCommitteeConfig(), None, workspace.runs_dir)
    generation.assert_not_called()
    assert git(path, "diff", "--cached", "--name-only") == "README.md"


def test_failed_run_loop_does_not_apply_or_publish(loop_workspace, monkeypatch):
    workspace = loop_workspace
    generation = Mock(side_effect=RuntimeError("no eligible question"))
    monkeypatch.setattr(uber_loop, "run_loop", generation)
    with pytest.raises(RuntimeError, match="no eligible question"):
        uber_loop.run_uber_loop(workspace.repo, ModelCommitteeConfig(), None, workspace.runs_dir)
    generation.assert_called_once()
    assert git(workspace.repo, "log", "--format=%s") == "Initial commit"
    assert git(workspace.artifacts, "log", "--format=%s") == "Initial commit"
    assert not (workspace.artifacts / "runs").exists()


@pytest.mark.parametrize(
    "invalid_output", ["missing-patch", "missing-message", "forbidden-patch", "existing-artifact"]
)
def test_invalid_output_stops_before_applying(loop_workspace, monkeypatch, invalid_output):
    workspace = loop_workspace
    run_dir = write_run(workspace, "invalid-run", "Initial design", "Updated design")
    if invalid_output == "missing-patch":
        (run_dir / "patches" / "selected.patch").unlink()
    elif invalid_output == "missing-message":
        (run_dir / "commit_message.txt").unlink()
    elif invalid_output == "forbidden-patch":
        patch = run_dir / "patches" / "selected.patch"
        patch.write_text(
            patch.read_text(encoding="utf-8").replace("DESIGN.md", "README.md"), encoding="utf-8"
        )
    else:
        (workspace.artifacts / "runs" / run_dir.name).mkdir(parents=True)
    generation = Mock(return_value=run_dir)
    monkeypatch.setattr(uber_loop, "run_loop", generation)
    with pytest.raises((OSError, RuntimeError, PatchValidationError)):
        uber_loop.run_uber_loop(workspace.repo, ModelCommitteeConfig(), None, workspace.runs_dir)
    generation.assert_called_once()
    assert git(workspace.repo, "status", "--porcelain") == ""
    assert git(workspace.repo, "log", "--format=%s") == "Initial commit"
    assert git(workspace.artifacts, "log", "--format=%s") == "Initial commit"


def test_cli_accepts_and_forwards_all_run_loop_parameters(monkeypatch):
    options = [
        "--repo",
        "design repo",
        "--config",
        "config path.json",
        "--runs-dir",
        "custom runs",
        "--fake-providers",
        "--phase",
        "Phase 4",
    ]
    parser = cli.build_parser()
    loop_args = vars(parser.parse_args(["run-loop", *options]))
    uber_args = vars(parser.parse_args(["uber-loop", *options]))
    assert {key: value for key, value in uber_args.items() if key != "command"} == {
        key: value for key, value in loop_args.items() if key != "command"
    }
    config = ModelCommitteeConfig()
    load_config = Mock(return_value=config)
    run = Mock()
    monkeypatch.setattr(cli, "load_config", load_config)
    monkeypatch.setattr(cli, "run_uber_loop", run)
    assert cli.main(["uber-loop", *options]) == 0
    load_config.assert_called_once_with(Path("config path.json"))
    run.assert_called_once_with(
        Path("design repo"),
        config,
        Path("config path.json"),
        Path("custom runs"),
        True,
        phase_filter="Phase 4",
    )


@pytest.mark.parametrize(
    ("error", "exit_code", "message"),
    [
        (RuntimeError("publication failed"), EXIT_RUNTIME_ERROR, "publication failed"),
        (KeyboardInterrupt(), EXIT_USER_CANCELED, "canceled"),
    ],
)
def test_cli_reports_failure_or_cancellation(monkeypatch, capsys, error, exit_code, message):
    monkeypatch.setattr(cli, "load_config", Mock(return_value=ModelCommitteeConfig()))
    monkeypatch.setattr(cli, "run_uber_loop", Mock(side_effect=error))
    assert cli.main(["uber-loop", "--repo", "../ubu-design"]) == exit_code
    assert message in capsys.readouterr().err
