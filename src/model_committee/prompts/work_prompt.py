import json
from pathlib import Path

from model_committee.constants import PROMPT_SIZE_WARNING_LIMIT
from model_committee.context.closure import ClosureResult, RepoContext, compute_closure
from model_committee.context.render import next_free_ids, render_excerpts
from model_committee.responses.schema_files import WORK_PROPOSAL_SCHEMA


def render_work_prompt(repo: Path, question, base_commit: str) -> tuple[str, bool, ClosureResult]:
    template = Path("prompts/work_prompt.md").read_text(encoding="utf-8")
    context = RepoContext.load(repo)
    closure = compute_closure(context, question.question_id)
    next_question_id, next_decision_id = next_free_ids(context)
    rendered = template.format(
        question_id=question.question_id,
        question_title=question.title,
        question_block=question.block,
        base_commit=base_commit,
        context_excerpts=render_excerpts(
            context, closure, exclude_question_id=question.question_id
        ),
        next_question_id=next_question_id,
        next_decision_id=next_decision_id,
        work_proposal_schema=json.dumps(WORK_PROPOSAL_SCHEMA, indent=2),
    )
    return rendered, len(rendered) >= int(0.9 * PROMPT_SIZE_WARNING_LIMIT), closure
