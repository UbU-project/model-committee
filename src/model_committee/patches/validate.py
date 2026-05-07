import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel

from model_committee.errors import PatchValidationError
from model_committee.patches.extract import enforce_allowed_patch_files


class PatchValidationResult(BaseModel):
    proposal_id: str
    patch_applies: bool
    allowlist_passed: bool
    changed_files: list[str]
    error: str | None = None


def validate_patch(repo: Path, proposal_id: str, patch: str) -> PatchValidationResult:
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
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as patch_file:
        patch_file.write(patch)
        patch_path = Path(patch_file.name)
    result = subprocess.run(
        ["git", "-C", str(repo), "apply", "--check", str(patch_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    patch_path.unlink(missing_ok=True)
    if result.returncode != 0:
        return PatchValidationResult(
            proposal_id=proposal_id,
            patch_applies=False,
            allowlist_passed=True,
            changed_files=changed_files,
            error=result.stderr.strip() or result.stdout.strip(),
        )
    return PatchValidationResult(
        proposal_id=proposal_id,
        patch_applies=True,
        allowlist_passed=True,
        changed_files=changed_files,
    )
