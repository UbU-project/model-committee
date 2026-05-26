import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from model_committee.constants import ALLOWED_PATCH_FILES
from model_committee.errors import PatchValidationError
from model_committee.patches.extract import enforce_allowed_patch_files

ALLOWED_PATCH_FILE_ORDER = (
    "DESIGN.md",
    "DECISIONS.md",
    "OPEN_QUESTIONS.md",
    "PLANNING_KERNEL_CONTRACT.md",
)
RECOUNT_NORMALIZATION_WARNING = "Patch required --recount normalization."
POSIX_NORMALIZATION_WARNING = "Patch normalized from POSIX unified diff to git extended format."


class PatchValidationResult(BaseModel):
    proposal_id: str
    patch_applies: bool
    allowlist_passed: bool
    changed_files: list[str]
    error: str | None = None
    normalized_patch: str | None = None
    warnings: list[str] = Field(default_factory=list)
    ordinary_error: str | None = None
    recount_error: str | None = None
    normalization_error: str | None = None


def _result_text(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip() or f"git exited with {result.returncode}"


def _combined_error(*items: tuple[str, str | None]) -> str:
    return "\n".join(f"{label}: {message}" for label, message in items if message)


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _run_git_apply(
    repo: Path, patch: str, apply_args: list[str]
) -> subprocess.CompletedProcess[str]:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as patch_file:
        patch_file.write(patch)
        patch_path = Path(patch_file.name)
    try:
        return _run_git(["git", "-C", str(repo), "apply", *apply_args, str(patch_path)])
    finally:
        patch_path.unlink(missing_ok=True)


def _create_temp_validation_repo(source_repo: Path, target_repo: Path) -> str | None:
    shutil.copytree(
        source_repo,
        target_repo,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git"),
    )
    init = _run_git(["git", "-C", str(target_repo), "init", "--quiet"])
    if init.returncode != 0:
        return _result_text(init)
    add = _run_git(["git", "-C", str(target_repo), "add", "--all"])
    if add.returncode != 0:
        return _result_text(add)
    return None


def _changed_paths(repo: Path) -> tuple[list[str], str | None]:
    diff = _run_git(["git", "-C", str(repo), "diff", "--name-only", "--", "."])
    if diff.returncode != 0:
        return [], _result_text(diff)
    untracked = _run_git(["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"])
    if untracked.returncode != 0:
        return [], _result_text(untracked)
    paths = set(diff.stdout.splitlines()) | set(untracked.stdout.splitlines())
    return sorted(path for path in paths if path), None


def _normalize_patch_with_recount(
    repo: Path, patch: str
) -> tuple[str | None, list[str], str | None]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_repo = Path(temp_dir) / "repo"
        setup_error = _create_temp_validation_repo(repo, temp_repo)
        if setup_error:
            return None, [], setup_error

        apply = _run_git_apply(temp_repo, patch, ["--recount"])
        if apply.returncode != 0:
            return None, [], _result_text(apply)

        changed_paths, paths_error = _changed_paths(temp_repo)
        if paths_error:
            return None, [], paths_error
        forbidden = sorted(path for path in changed_paths if path not in ALLOWED_PATCH_FILES)
        if forbidden:
            return None, [], f"normalization changed forbidden files: {', '.join(forbidden)}"

        diff = _run_git(
            [
                "git",
                "-C",
                str(temp_repo),
                "diff",
                "--no-ext-diff",
                "--",
                *ALLOWED_PATCH_FILE_ORDER,
            ]
        )
        if diff.returncode != 0:
            return None, [], _result_text(diff)
        normalized_patch = diff.stdout
        if not normalized_patch.strip():
            return None, [], "recount normalization produced an empty patch"

        try:
            changed_files = enforce_allowed_patch_files(normalized_patch)
        except PatchValidationError as exc:
            return None, [], str(exc)
        return normalized_patch, changed_files, None


def validate_patch(repo: Path, proposal_id: str, patch: str) -> PatchValidationResult:
    if "diff --git" not in patch:
        normalized_patch, normalized_changed_files, normalization_error = (
            _normalize_patch_with_recount(repo, patch)
        )
        if normalization_error or normalized_patch is None:
            return PatchValidationResult(
                proposal_id=proposal_id,
                patch_applies=False,
                allowlist_passed=False,
                changed_files=[],
                error=normalization_error or "POSIX normalization produced no output",
                normalization_error=normalization_error,
            )
        return PatchValidationResult(
            proposal_id=proposal_id,
            patch_applies=True,
            allowlist_passed=True,
            changed_files=normalized_changed_files,
            normalized_patch=normalized_patch,
            warnings=[POSIX_NORMALIZATION_WARNING],
        )

    try:
        changed_files = enforce_allowed_patch_files(patch)
    except PatchValidationError as exc:
        return PatchValidationResult(
            proposal_id=proposal_id,
            patch_applies=False,
            allowlist_passed=False,
            changed_files=[],
            error=str(exc),
        )

    ordinary = _run_git_apply(repo, patch, ["--check"])
    if ordinary.returncode == 0:
        return PatchValidationResult(
            proposal_id=proposal_id,
            patch_applies=True,
            allowlist_passed=True,
            changed_files=changed_files,
        )

    ordinary_error = _result_text(ordinary)
    recount = _run_git_apply(repo, patch, ["--check", "--recount"])
    if recount.returncode != 0:
        recount_error = _result_text(recount)
        return PatchValidationResult(
            proposal_id=proposal_id,
            patch_applies=False,
            allowlist_passed=True,
            changed_files=changed_files,
            error=_combined_error(
                ("ordinary git apply --check failed", ordinary_error),
                ("git apply --check --recount failed", recount_error),
            ),
            ordinary_error=ordinary_error,
            recount_error=recount_error,
        )

    normalized_patch, normalized_changed_files, normalization_error = _normalize_patch_with_recount(
        repo, patch
    )
    if normalization_error or normalized_patch is None:
        return PatchValidationResult(
            proposal_id=proposal_id,
            patch_applies=False,
            allowlist_passed=True,
            changed_files=changed_files,
            error=_combined_error(
                ("ordinary git apply --check failed", ordinary_error),
                ("git apply --recount normalization failed", normalization_error),
            ),
            ordinary_error=ordinary_error,
            normalization_error=normalization_error,
        )

    normalized_check = _run_git_apply(repo, normalized_patch, ["--check"])
    if normalized_check.returncode != 0:
        normalized_check_error = _result_text(normalized_check)
        return PatchValidationResult(
            proposal_id=proposal_id,
            patch_applies=False,
            allowlist_passed=True,
            changed_files=normalized_changed_files,
            error=_combined_error(
                ("ordinary git apply --check failed", ordinary_error),
                ("normalized git apply --check failed", normalized_check_error),
            ),
            ordinary_error=ordinary_error,
            normalization_error=normalized_check_error,
        )
    return PatchValidationResult(
        proposal_id=proposal_id,
        patch_applies=True,
        allowlist_passed=True,
        changed_files=normalized_changed_files,
        normalized_patch=normalized_patch,
        warnings=[RECOUNT_NORMALIZATION_WARNING],
        ordinary_error=ordinary_error,
    )
