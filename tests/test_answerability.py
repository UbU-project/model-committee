from model_committee.markdown.questions_parser import parse_questions_file, parse_questions_text
from model_committee.ranking.answerability import compute_answerability
from model_committee.ranking.ranker import rank_questions


def test_answerability_scores():
    questions = parse_questions_file("tests/fixtures/valid_repo/OPEN_QUESTIONS.md")
    by_id = {question.question_id: question for question in questions}
    assert compute_answerability(by_id["UBU-Q0001"], by_id) == 100
    assert compute_answerability(by_id["UBU-Q0003"], by_id) == 50


def test_rank_selects_top_eligible_question():
    report = rank_questions(parse_questions_file("tests/fixtures/valid_repo/OPEN_QUESTIONS.md"))
    assert report.selected_question_id == "UBU-Q0001"


def _question_block(
    question_id: str,
    title: str,
    *,
    status: str = "Open",
    phase: str = "Phase 1",
    automation_likelihood_score: int = 80,
    importance_score: int = 80,
    risk_score: int = 20,
    depends_on: str = "None",
) -> str:
    return f"""## {question_id}: {title}

Status: {status} Priority: MVP important Phase: {phase} Decision type: Process Auto-choice eligibility: Auto eligible Importance score: {importance_score} Automation-likelihood score: {automation_likelihood_score} Risk score: {risk_score} Answerability score: TBD Depends on: {depends_on} Blocks: None Resolved by: Unresolved Last scored: Never Scored from commit: None

### Question

What should happen?

### Current direction

Keep the change small.

### Resolution

Unresolved.
"""


def test_rank_sorts_automation_likelihood_before_open_dependent_count():
    questions = parse_questions_text(
        "# Open Questions\n\n"
        + _question_block("UBU-Q0001", "More Dependents", automation_likelihood_score=80)
        + "\n"
        + _question_block("UBU-Q0002", "More Automatable", automation_likelihood_score=90)
        + "\n"
        + _question_block("UBU-Q0003", "Open Dependent", depends_on="UBU-Q0001")
    )

    report = rank_questions(questions)

    assert [question.question_id for question in report.ranked_questions[:2]] == [
        "UBU-Q0002",
        "UBU-Q0001",
    ]
    assert report.selected_question_id == "UBU-Q0002"


def test_phase_filter_excludes_non_matching_questions():
    questions = parse_questions_text(
        "# Open Questions\n\n"
        + _question_block("UBU-Q0001", "Phase 1 Question", phase="Phase 1")
        + "\n"
        + _question_block("UBU-Q0002", "Phase 2 Question", phase="Phase 2")
        + "\n"
        + _question_block("UBU-Q0003", "Another Phase 1", phase="Phase 1")
    )

    report = rank_questions(questions, phase_filter="Phase 1")

    ids = [q.question_id for q in report.ranked_questions]
    assert "UBU-Q0001" in ids
    assert "UBU-Q0003" in ids
    assert "UBU-Q0002" not in ids
    assert report.phase_filter == "Phase 1"


def test_phase_filter_empty_result_when_no_matching_questions():
    questions = parse_questions_text(
        "# Open Questions\n\n" + _question_block("UBU-Q0001", "Phase 1 Question", phase="Phase 1")
    )

    report = rank_questions(questions, phase_filter="Phase 2")

    assert report.ranked_questions == []
    assert report.selected_question_id is None
    assert report.phase_filter == "Phase 2"


def test_phase_filter_none_ranks_all_phases():
    questions = parse_questions_text(
        "# Open Questions\n\n"
        + _question_block("UBU-Q0001", "Phase 1 Question", phase="Phase 1")
        + "\n"
        + _question_block("UBU-Q0002", "Phase 2 Question", phase="Phase 2")
    )

    report = rank_questions(questions, phase_filter=None)

    ids = [q.question_id for q in report.ranked_questions]
    assert "UBU-Q0001" in ids
    assert "UBU-Q0002" in ids
    assert report.phase_filter is None


def test_rank_sorts_open_dependent_count_before_importance_and_question_id():
    questions = parse_questions_text(
        "# Open Questions\n\n"
        + _question_block(
            "UBU-Q0001",
            "Earlier Higher Importance",
            automation_likelihood_score=80,
            importance_score=100,
        )
        + "\n"
        + _question_block(
            "UBU-Q0002",
            "Blocks Open Question",
            automation_likelihood_score=80,
            importance_score=10,
        )
        + "\n"
        + _question_block("UBU-Q0003", "Open Dependent", depends_on="UBU-Q0002")
        + "\n"
        + _question_block(
            "UBU-Q0004",
            "Solved Dependent",
            status="Solved",
            depends_on="UBU-Q0001",
        )
    )

    report = rank_questions(questions)

    assert [question.question_id for question in report.ranked_questions[:2]] == [
        "UBU-Q0002",
        "UBU-Q0001",
    ]
    assert report.selected_question_id == "UBU-Q0002"
