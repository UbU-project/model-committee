from model_committee.markdown.questions_parser import Question
from model_committee.ranking.answerability import compute_answerability, is_work_eligible
from model_committee.responses.schemas import RankedQuestion, RankingReport


def rank_questions(questions: list[Question]) -> RankingReport:
    by_id = {question.question_id: question for question in questions}
    open_questions = [question for question in questions if question.metadata.status == "Open"]
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
            q.importance_score or -1,
            -(q.risk_score or 101),
            q.question_id,
        ),
        reverse=True,
    )
    selected = next(
        (q.question_id for q in ranked if is_work_eligible(q.answerability_score)), None
    )
    return RankingReport(status="ok", ranked_questions=ranked, selected_question_id=selected)
