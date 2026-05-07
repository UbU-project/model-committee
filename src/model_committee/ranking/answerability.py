from model_committee.markdown.questions_parser import Question


def compute_answerability(question: Question, questions_by_id: dict[str, Question]) -> int:
    if not question.metadata.depends_on:
        return 100
    if all(
        questions_by_id[dep].metadata.status == "Solved" for dep in question.metadata.depends_on
    ):
        return 90
    if question.metadata.auto_choice_eligibility == "Auto eligible":
        return 50
    return 0


def is_work_eligible(score: int) -> bool:
    return score >= 90 or score == 50
