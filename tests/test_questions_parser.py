import pytest

from model_committee.errors import ParseError
from model_committee.markdown.questions_parser import parse_questions_file


def test_parse_valid_questions():
    questions = parse_questions_file("tests/fixtures/valid_repo/OPEN_QUESTIONS.md")
    assert [question.question_id for question in questions] == [
        "UBU-Q0001",
        "UBU-Q0002",
        "UBU-Q0003",
    ]
    assert questions[0].metadata.importance_score is None
    assert questions[0].metadata.depends_on == []


def test_parse_unknown_label_reports_missing_and_unknown():
    with pytest.raises(ParseError) as exc:
        parse_questions_file("tests/fixtures/invalid_unknown_label/OPEN_QUESTIONS.md")
    assert "Missing required field: Auto-choice eligibility" in str(exc.value)
    assert "Unknown or unparsed metadata segment near: Auto choice eligibility" in str(exc.value)
