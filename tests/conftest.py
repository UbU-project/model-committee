import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture()
def git_fixture_repo(tmp_path: Path) -> Path:
    src = Path("tests/fixtures/valid_repo")
    repo = tmp_path / "repo"
    shutil.copytree(src, repo)
    subprocess.run(["git", "-C", str(repo), "init"], check=True, stdout=subprocess.PIPE)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "fixture"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return repo
