import re
from pathlib import Path

from model_committee.constants import ALLOWED_PATCH_FILES
from model_committee.errors import PatchValidationError

DIFF_HEADER_RE = re.compile(r"^diff --git (.+?) (.+?)$", re.MULTILINE)


def normalize_patch_path(path: str) -> str:
    if path == "/dev/null":
        return path
    if path.startswith(("a/", "b/")):
        path = path[2:]
    if path.startswith("/") or ".." in Path(path).parts:
        raise PatchValidationError(f"forbidden patch path: {path}")
    if any(part.startswith(".") for part in Path(path).parts):
        raise PatchValidationError(f"hidden patch path forbidden: {path}")
    return path


def changed_files_from_patch(patch: str) -> list[str]:
    if not patch.strip():
        raise PatchValidationError("patch is empty")
    if "diff --git" not in patch:
        raise PatchValidationError("patch has no diff --git header")
    files: set[str] = set()
    for match in DIFF_HEADER_RE.finditer(patch):
        left = normalize_patch_path(match.group(1))
        right = normalize_patch_path(match.group(2))
        for path in (left, right):
            if path != "/dev/null":
                files.add(path)
    if not files:
        raise PatchValidationError("patch has no changed files")
    return sorted(files)


def enforce_allowed_patch_files(patch: str) -> list[str]:
    files = changed_files_from_patch(patch)
    forbidden = [path for path in files if path not in ALLOWED_PATCH_FILES]
    if forbidden:
        raise PatchValidationError(f"patch modifies forbidden files: {', '.join(forbidden)}")
    return files
