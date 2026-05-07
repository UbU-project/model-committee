from collections import Counter
from pathlib import Path

from model_committee.consistency.decision_refs import nonexistent_decision_refs
from model_committee.consistency.question_graph import dependency_edges, find_dependency_cycles
from model_committee.errors import ParseError
from model_committee.markdown.decisions_parser import parse_decisions_file
from model_committee.markdown.questions_parser import parse_questions_file
from model_committee.responses.schemas import ConsistencyIssue, ConsistencyReport


def check_repo(repo: Path) -> ConsistencyReport:
    repo = Path(repo)
    hard: list[ConsistencyIssue] = []
    warnings: list[ConsistencyIssue] = []
    try:
        questions = parse_questions_file(repo / "OPEN_QUESTIONS.md")
        decisions = parse_decisions_file(repo / "DECISIONS.md")
    except ParseError as exc:
        text = str(exc)
        code = (
            "MISSING_REQUIRED_METADATA"
            if "Missing required field" in text
            else "INVALID_ENUM_VALUE"
        )
        return ConsistencyReport(
            status="failed",
            hard_failures=[ConsistencyIssue(code=code, message=text)],
            warnings=[],
            question_count=0,
            decision_count=0,
            dependency_edges=[],
        )

    question_counts = Counter(question.question_id for question in questions)
    for question_id, count in question_counts.items():
        if count > 1:
            hard.append(
                ConsistencyIssue(
                    code="DUPLICATE_QUESTION_ID",
                    message=f"Duplicate question ID: {question_id}",
                    question_id=question_id,
                )
            )

    decision_counts = Counter(decision.decision_id for decision in decisions)
    for decision_id, count in decision_counts.items():
        if count > 1:
            hard.append(
                ConsistencyIssue(
                    code="DUPLICATE_DECISION_ID",
                    message=f"Duplicate decision ID: {decision_id}",
                    decision_id=decision_id,
                )
            )

    question_ids = set(question_counts)
    for question in questions:
        if (
            question.metadata.importance_score is None
            or question.metadata.automation_likelihood_score is None
            or question.metadata.risk_score is None
            or question.metadata.answerability_score is None
        ):
            warnings.append(
                ConsistencyIssue(
                    code="QUESTION_SCORE_TBD",
                    message=f"{question.question_id} has TBD scores.",
                    question_id=question.question_id,
                )
            )
        if not question.has_current_direction:
            warnings.append(
                ConsistencyIssue(
                    code="QUESTION_HAS_NO_CURRENT_DIRECTION",
                    message=f"{question.question_id} has no Current direction.",
                    question_id=question.question_id,
                )
            )
        for dependency in question.metadata.depends_on:
            if dependency not in question_ids:
                hard.append(
                    ConsistencyIssue(
                        code="NONEXISTENT_DEPENDENCY",
                        message=f"{question.question_id} depends on nonexistent {dependency}",
                        question_id=question.question_id,
                    )
                )

    for cycle in find_dependency_cycles(questions):
        hard.append(
            ConsistencyIssue(
                code="QUESTION_DEPENDENCY_CYCLE",
                message="Question dependency cycle: " + " -> ".join(cycle),
                question_id=cycle[0],
            )
        )

    for question_id, decision_id in nonexistent_decision_refs(questions, decisions):
        hard.append(
            ConsistencyIssue(
                code="NONEXISTENT_DECISION_REFERENCE",
                message=f"{question_id} resolved by nonexistent {decision_id}",
                question_id=question_id,
                decision_id=decision_id,
            )
        )

    return ConsistencyReport(
        status="failed" if hard else "passed",
        hard_failures=hard,
        warnings=warnings,
        question_count=len(questions),
        decision_count=len(decisions),
        dependency_edges=dependency_edges(questions),
    )
