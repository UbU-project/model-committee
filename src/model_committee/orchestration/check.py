from pathlib import Path

from model_committee.consistency.checker import check_repo
from model_committee.responses.schemas import ConsistencyReport


def run_check(repo: Path) -> ConsistencyReport:
    return check_repo(repo)
