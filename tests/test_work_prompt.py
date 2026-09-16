from pathlib import Path

from model_committee.markdown.questions_parser import parse_questions_file
from model_committee.prompts.score_prompt import render_score_prompt
from model_committee.prompts.work_prompt import render_work_prompt


def test_work_prompt_requires_raw_git_diff_and_selected_question_anchor():
    repo = Path("tests/fixtures/valid_repo")
    question = {
        item.question_id: item for item in parse_questions_file(repo / "OPEN_QUESTIONS.md")
    }["UBU-Q0001"]

    prompt, warn = render_work_prompt(repo, question, "fixture")

    assert warn is False
    assert "Do not include hidden reasoning, `<think>` tags" in prompt
    assert "The `patch` string must be a raw unified diff as produced by `git diff`" in prompt
    assert "git apply --check" in prompt
    assert "## UBU-Q0001: Example Question" in prompt
    assert "its own `### Resolution` section" in prompt
    assert (
        "Do not insert selected-question resolution text into any other question block." in prompt
    )


def test_score_prompt_includes_static_provider_weights():
    repo = Path("tests/fixtures/valid_repo")
    question = {
        item.question_id: item for item in parse_questions_file(repo / "OPEN_QUESTIONS.md")
    }["UBU-Q0001"]

    prompt, warn = render_score_prompt(
        question,
        "fixture",
        [],
        [],
        {"codex": 1.0, "ollama:local": 0.35},
    )

    assert warn is False
    assert "## Provider weights" in prompt
    assert '"codex": 1.0' in prompt
    assert "historical diagnostic context only in v0.2" in prompt


def test_work_prompt_renders_excerpts_not_whole_files():
    repo = Path("tests/fixtures/valid_repo")
    question = {
        item.question_id: item for item in parse_questions_file(repo / "OPEN_QUESTIONS.md")
    }["UBU-Q0003"]

    prompt, _ = render_work_prompt(repo, question, "fixture")

    # UBU-Q0003 depends on UBU-Q0001, so that dependency is included as an excerpt
    assert "#### UBU-Q0001" in prompt
    # ...but the unrelated UBU-Q0002 is not pulled in
    assert "#### UBU-Q0002" not in prompt
    # the selected question is shown under "Selected question", not repeated as an excerpt
    assert "#### UBU-Q0003" not in prompt


def test_work_prompt_states_excerpts_are_partial():
    repo = Path("tests/fixtures/valid_repo")
    question = {
        item.question_id: item for item in parse_questions_file(repo / "OPEN_QUESTIONS.md")
    }["UBU-Q0001"]

    prompt, _ = render_work_prompt(repo, question, "fixture")

    assert "are **not** the whole canonical files" in prompt
    assert "Absence is not non-existence" in prompt


def test_work_prompt_injects_next_free_ids():
    repo = Path("tests/fixtures/valid_repo")
    question = {
        item.question_id: item for item in parse_questions_file(repo / "OPEN_QUESTIONS.md")
    }["UBU-Q0001"]

    prompt, _ = render_work_prompt(repo, question, "fixture")

    # fixture has UBU-Q0001..UBU-Q0003 and UBU-D0001
    assert "next question id: `UBU-Q0004`" in prompt
    assert "next decision id: `UBU-D0002`" in prompt
