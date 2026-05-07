from model_committee.markdown.questions_parser import parse_questions_file
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
