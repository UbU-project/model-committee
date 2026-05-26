import json
from pathlib import Path

from pydantic import BaseModel

from model_committee.constants import ALLOWED_PATCH_FILES


WORK_PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "proposal_id",
        "provider_id",
        "model_name",
        "question_id",
        "base_commit",
        "summary",
        "rationale",
        "changed_files",
        "patch",
        "commit_message",
        "validation_notes",
        "new_questions_added",
        "questions_resolved",
        "decisions_added",
        "requires_human_review",
    ],
    "properties": {
        "proposal_id": {"type": "string"},
        "provider_id": {"type": "string"},
        "model_name": {"type": "string"},
        "question_id": {"type": "string", "pattern": "^UBU-Q[0-9]{4}$"},
        "base_commit": {"type": "string"},
        "summary": {"type": "string"},
        "rationale": {"type": "string"},
        "changed_files": {
            "type": "array",
            "items": {"type": "string", "enum": sorted(ALLOWED_PATCH_FILES)},
        },
        "patch": {"type": "string"},
        "commit_message": {"type": "string"},
        "validation_notes": {"type": "array", "items": {"type": "string"}},
        "new_questions_added": {
            "type": "array",
            "items": {"type": "string", "pattern": "^UBU-Q[0-9]{4}$"},
        },
        "questions_resolved": {
            "type": "array",
            "items": {"type": "string", "pattern": "^UBU-Q[0-9]{4}$"},
        },
        "decisions_added": {
            "type": "array",
            "items": {"type": "string", "pattern": "^UBU-D[0-9]{4}$"},
        },
        "requires_human_review": {"type": "boolean"},
    },
}

SCORE_RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["scores", "selected_proposal_id", "selection_rationale"],
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "proposal_id",
                    "score",
                    "patch_applies",
                    "implements_selected_work",
                    "preserves_question_schema",
                    "avoids_unnecessary_scope",
                    "decomposition_quality",
                    "risks",
                    "required_fixes",
                    "rationale",
                ],
                "properties": {
                    "proposal_id": {"type": "string"},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "patch_applies": {"type": "boolean"},
                    "implements_selected_work": {"type": "boolean"},
                    "preserves_question_schema": {"type": "boolean"},
                    "avoids_unnecessary_scope": {"type": "boolean"},
                    "decomposition_quality": {
                        "type": "string",
                        "enum": ["none", "good", "bad", "not_applicable"],
                    },
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "required_fixes": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
            },
        },
        "selected_proposal_id": {"type": "string"},
        "selection_rationale": {"type": "string"},
    },
}


class SchemaPaths(BaseModel):
    work_proposal_schema: Path
    score_result_schema: Path


def _write_schema(path: Path, schema: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def write_work_proposal_schema(path: Path) -> None:
    _write_schema(path, WORK_PROPOSAL_SCHEMA)


def write_score_result_schema(path: Path) -> None:
    _write_schema(path, SCORE_RESULT_SCHEMA)


def copy_schema_files_to_run(run_dir: Path) -> SchemaPaths:
    schema_dir = run_dir / "schemas"
    work = schema_dir / "work_proposal.schema.json"
    score = schema_dir / "score_result.schema.json"
    write_work_proposal_schema(work)
    write_score_result_schema(score)
    return SchemaPaths(work_proposal_schema=work, score_result_schema=score)
