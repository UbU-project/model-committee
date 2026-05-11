import json
from pathlib import Path

from model_committee.constants import PROMPT_SIZE_WARNING_LIMIT
from model_committee.responses.schema_files import SCORE_RESULT_SCHEMA


def render_score_prompt(
    question,
    base_commit: str,
    candidate_proposals: list[dict],
    patch_validation_results: list[dict],
    provider_weights: dict[str, float] | None = None,
) -> tuple[str, bool]:
    template = Path("prompts/score_prompt.md").read_text(encoding="utf-8")
    rendered = template.format(
        question_id=question.question_id,
        question_title=question.title,
        question_block=question.block,
        base_commit=base_commit,
        candidate_proposals_json=json.dumps(candidate_proposals, indent=2),
        patch_validation_results_json=json.dumps(patch_validation_results, indent=2),
        provider_weights_json=json.dumps(provider_weights or {}, indent=2),
        score_result_schema=json.dumps(SCORE_RESULT_SCHEMA, indent=2),
    )
    return rendered, len(rendered) > PROMPT_SIZE_WARNING_LIMIT
