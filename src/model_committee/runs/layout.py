import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from model_committee.constants import REQUIRED_REPO_FILES
from model_committee.runs.manifest import RunManifest, RunStatus, utc_now_text, write_manifest


def get_base_commit(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return "unknown"


def make_run_id(question_id: str) -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"-{question_id}"


def create_run_dir(
    runs_root: Path,
    repo: Path,
    question_id: str,
    config_path: Path | None,
    command: str,
) -> tuple[Path, RunManifest]:
    run_id = make_run_id(question_id)
    run_dir = runs_root / run_id
    for name in ("snapshot", "schemas", "prompts", "responses", "parsed", "patches"):
        (run_dir / name).mkdir(parents=True, exist_ok=True)
    for filename in REQUIRED_REPO_FILES:
        shutil.copy2(repo / filename, run_dir / "snapshot" / filename)
    manifest = RunManifest(
        run_id=run_id,
        created_at_utc=utc_now_text(),
        repo_path=str(repo),
        base_commit=get_base_commit(repo),
        selected_question_id=question_id,
        phase="work-generate",
        config_path=str(config_path) if config_path else None,
        status=RunStatus.IN_PROGRESS,
        commands=[command],
    )
    write_manifest(run_dir, manifest)
    return run_dir, manifest
