import shlex
import shutil
import subprocess
from pathlib import Path

from model_committee.config import ModelCommitteeConfig
from model_committee.errors import PatchValidationError
from model_committee.orchestration.run_loop import run_loop
from model_committee.patches.extract import enforce_allowed_patch_files
from model_committee.patches.validate import validate_patch


def _git(repo: Path, *args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo), *args]
    try:
        return subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE if capture_output else None,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"uber-loop command failed (exit {exc.returncode}): {shlex.join(command)}"
        ) from exc


def _require_empty_index(repo: Path) -> None:
    result = _git(repo, "diff", "--cached", "--name-only", capture_output=True)
    if result.stdout.strip():
        raise RuntimeError(f"uber-loop requires no staged changes in {repo}")


def run_uber_loop(
    repo: Path,
    config: ModelCommitteeConfig,
    config_path: Path | None,
    runs_dir: Path,
    fake_providers: bool = False,
    phase_filter: str | None = None,
) -> None:
    """Repeat selection, signed design commits, and artifact publication until failure."""
    artifacts_repo = Path("../model-committee-artifacts").resolve()
    while True:
        # Commits consume the whole index, so never include previously staged work.
        # Unstaged changes are allowed: ranking itself updates OPEN_QUESTIONS.md.
        _require_empty_index(repo)
        _require_empty_index(artifacts_repo)
        run_dir = run_loop(
            repo,
            config,
            config_path,
            runs_dir,
            fake_providers,
            phase_filter=phase_filter,
        ).resolve(strict=True)
        print(run_dir.name, flush=True)

        patch_path = (run_dir / "patches" / "selected.patch").resolve(strict=True)
        message_path = (run_dir / "commit_message.txt").resolve(strict=True)
        patch = patch_path.read_text(encoding="utf-8")
        changed_files = enforce_allowed_patch_files(patch)
        destination = artifacts_repo / "runs" / run_dir.name
        if destination.exists():
            raise RuntimeError(f"artifact run already exists: {destination}")

        validation = validate_patch(repo, run_dir.name, patch)
        if not validation.valid:
            raise PatchValidationError(validation.error or "selected patch failed validation")
        _git(repo, "apply", str(patch_path))
        _git(repo, "add", "--", *changed_files)
        _git(repo, "commit", "-S", "-F", str(message_path))

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(run_dir, destination)
        _git(artifacts_repo, "add", "--", f"runs/{run_dir.name}")
        _git(artifacts_repo, "commit", "-S", "-m", f"UMC artifact {run_dir.name}")
        _git(artifacts_repo, "push")
