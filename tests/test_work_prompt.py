from pathlib import Path

from model_committee.markdown.questions_parser import parse_questions_file
from model_committee.prompts.work_prompt import render_work_prompt


def test_work_prompt_requires_raw_git_diff_and_selected_question_anchor():
    repo = Path("tests/fixtures/valid_repo")
    question = {
        item.question_id: item for item in parse_questions_file(repo / "OPEN_QUESTIONS.md")
    }["UBU-Q0001"]

    prompt, warn = render_work_prompt(repo, question, "fixture")

    assert warn is False
    assert "The `patch` string must be a raw unified diff as produced by `git diff`" in prompt
    assert "git apply --check" in prompt
    assert "## UBU-Q0001: Example Question" in prompt
    assert "its own `### Resolution` section" in prompt
    assert "Do not insert selected-question resolution text into any other question block." in prompt
