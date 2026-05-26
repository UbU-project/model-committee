from datetime import date
from pathlib import Path

from model_committee.consistency.checker import check_repo
from model_committee.errors import ConsistencyError
from model_committee.markdown.questions_parser import parse_questions_file, update_question_scores
from model_committee.ranking.ranker import rank_questions
from model_committee.responses.schemas import RankingReport


def run_rank(repo: Path, phase_filter: str | None = None) -> RankingReport:
    report = check_repo(repo)
    if report.hard_failures:
        raise ConsistencyError("hard consistency failure")
    questions_path = repo / "OPEN_QUESTIONS.md"
    ranking_report = rank_questions(parse_questions_file(questions_path), phase_filter=phase_filter)
    score_by_id = {
        ranked.question_id: ranked.answerability_score for ranked in ranking_report.ranked_questions
    }
    if score_by_id:
        original = questions_path.read_text(encoding="utf-8")
        updated = update_question_scores(original, score_by_id, date.today().isoformat())
        if updated != original:
            questions_path.write_text(updated, encoding="utf-8")
    return ranking_report
