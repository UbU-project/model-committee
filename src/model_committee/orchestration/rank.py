from pathlib import Path

from model_committee.consistency.checker import check_repo
from model_committee.errors import ConsistencyError
from model_committee.markdown.questions_parser import parse_questions_file
from model_committee.ranking.ranker import rank_questions
from model_committee.responses.schemas import RankingReport


def run_rank(repo: Path) -> RankingReport:
    report = check_repo(repo)
    if report.hard_failures:
        raise ConsistencyError("hard consistency failure")
    return rank_questions(parse_questions_file(repo / "OPEN_QUESTIONS.md"))
