import json
from pathlib import Path

from model_committee.constants import PROMPT_SIZE_WARNING_LIMIT
from model_committee.responses.schema_files import WORK_PROPOSAL_SCHEMA


def render_work_prompt(repo: Path, question, base_commit: str) -> tuple[str, bool]:
    template = Path("prompts/work_prompt.md").read_text(encoding="utf-8")
    rendered = template.format(
        question_id=question.question_id,
        question_title=question.title,
        question_block=question.block,
        base_commit=base_commit,
        design_md=(repo / "DESIGN.md").read_text(encoding="utf-8"),
        decisions_md=(repo / "DECISIONS.md").read_text(encoding="utf-8"),
        open_questions_md=(repo / "OPEN_QUESTIONS.md").read_text(encoding="utf-8"),
        work_proposal_schema=json.dumps(WORK_PROPOSAL_SCHEMA, indent=2),
    )
    return rendered, len(rendered) > PROMPT_SIZE_WARNING_LIMIT
