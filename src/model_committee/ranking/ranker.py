from model_committee.markdown.questions_parser import Question
from model_committee.ranking.answerability import compute_answerability, is_work_eligible
from model_committee.responses.schemas import RankedQuestion, RankingReport


def _open_dependent_counts(open_questions: list[Question]) -> dict[str, int]:
    open_question_ids = {question.question_id for question in open_questions}
    return {
        question_id: sum(
            question_id in other.metadata.depends_on
            for other in open_questions
            if other.question_id != question_id
        )
        for question_id in open_question_ids
    }


def _earlier_question_sort_key(question_id: str) -> int:
    return -int(question_id.removeprefix("UBU-Q"))


def rank_questions(questions: list[Question], phase_filter: str | None = None) -> RankingReport:
    by_id = {question.question_id: question for question in questions}
    open_questions = [question for question in questions if question.metadata.status == "Open"]
    if phase_filter is not None:
        open_questions = [q for q in open_questions if q.metadata.phase == phase_filter]
    dependent_counts = _open_dependent_counts(open_questions)
    ranked_models = [
        RankedQuestion(
            question_id=question.question_id,
            title=question.title,
            answerability_score=compute_answerability(question, by_id),
            automation_likelihood_score=question.metadata.automation_likelihood_score,
            importance_score=question.metadata.importance_score,
            risk_score=question.metadata.risk_score,
            rank_reason="No unresolved dependencies."
            if compute_answerability(question, by_id) >= 90
            else "Eligible for decomposition."
            if compute_answerability(question, by_id) == 50
            else "Blocked by unresolved dependencies.",
        )
        for question in open_questions
    ]
    ranked = sorted(
        ranked_models,
        key=lambda q: (
            q.answerability_score,
            q.automation_likelihood_score or -1,
            dependent_counts[q.question_id],
            q.importance_score or -1,
            -(q.risk_score or 101),
            _earlier_question_sort_key(q.question_id),
        ),
        reverse=True,
    )
    selected = next(
        (q.question_id for q in ranked if is_work_eligible(q.answerability_score)), None
    )
    return RankingReport(
        status="ok",
        ranked_questions=ranked,
        selected_question_id=selected,
        phase_filter=phase_filter,
    )
