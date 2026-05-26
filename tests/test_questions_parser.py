import pytest

from model_committee.errors import ParseError
from model_committee.markdown.questions_parser import (
    parse_questions_file,
    parse_questions_text,
    update_question_scores,
)


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


_TOMBSTONE_TEXT = """\
# Open Questions

## UBU-Q0099: Tombstoned Question

Status: Solved Priority: MVP important Phase: Phase 1 Decision type: Process Auto-choice eligibility: Auto eligible Importance score: 80 Automation-likelihood score: 70 Risk score: 20 Answerability score: 100 Depends on: None Blocks: None Resolved by: UBU-D0099 Last scored: 2026-05-26 Scored from commit: None
Resolved. See UBU-D0099.

---
"""


def test_parse_tombstone_format():
    questions = parse_questions_text(_TOMBSTONE_TEXT)
    assert len(questions) == 1
    q = questions[0]
    assert q.question_id == "UBU-Q0099"
    assert q.metadata.status == "Solved"
    assert q.metadata.resolved_by == ["UBU-D0099"]
    assert q.metadata.answerability_score == 100


_SCORE_WRITEBACK_TEXT = """\
# Open Questions

## UBU-Q0001: Example Question

Status: Open Priority: MVP important Phase: Phase 1 Decision type: Process Auto-choice eligibility: Auto eligible Importance score: TBD Automation-likelihood score: TBD Risk score: TBD Answerability score: TBD Depends on: None Blocks: None Resolved by: Unresolved Last scored: Never Scored from commit: None

### Question

What should happen?

## UBU-Q0002: Solved Question

Status: Solved Priority: MVP important Phase: Phase 1 Decision type: Process Auto-choice eligibility: Human approval required Importance score: 50 Automation-likelihood score: 50 Risk score: 10 Answerability score: 100 Depends on: None Blocks: None Resolved by: UBU-D0001 Last scored: Never Scored from commit: abc123

Resolved. See UBU-D0001.

---
"""


def test_update_question_scores_updates_open_only():
    updated = update_question_scores(
        _SCORE_WRITEBACK_TEXT,
        score_by_id={"UBU-Q0001": 90},
        scored_date="2026-05-26",
    )
    questions = parse_questions_text(updated)
    by_id = {q.question_id: q for q in questions}
    assert by_id["UBU-Q0001"].metadata.answerability_score == 90
    assert by_id["UBU-Q0001"].metadata.last_scored == "2026-05-26"
    assert by_id["UBU-Q0001"].metadata.scored_from_commit == "None"
    assert by_id["UBU-Q0002"].metadata.last_scored == "Never"
    assert by_id["UBU-Q0002"].metadata.scored_from_commit == "abc123"


def test_update_question_scores_no_change_when_not_in_map():
    updated = update_question_scores(
        _SCORE_WRITEBACK_TEXT,
        score_by_id={},
        scored_date="2026-05-26",
    )
    assert updated == _SCORE_WRITEBACK_TEXT


def test_update_question_scores_round_trip_parse():
    updated = update_question_scores(
        _SCORE_WRITEBACK_TEXT,
        score_by_id={"UBU-Q0001": 50},
        scored_date="2026-05-26",
    )
    questions = parse_questions_text(updated)
    assert len(questions) == 2
