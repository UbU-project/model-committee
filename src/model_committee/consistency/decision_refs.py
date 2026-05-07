from model_committee.markdown.decisions_parser import Decision
from model_committee.markdown.questions_parser import Question


def nonexistent_decision_refs(
    questions: list[Question], decisions: list[Decision]
) -> list[tuple[str, str]]:
    decision_ids = {decision.decision_id for decision in decisions}
    return [
        (question.question_id, decision_id)
        for question in questions
        for decision_id in question.metadata.resolved_by
        if decision_id not in decision_ids
    ]
