import json
from pathlib import Path

from model_committee.errors import SelectionError
from model_committee.patches.validate import PatchValidationResult
from model_committee.responses.schemas import ScoreResult, WorkProposal
from model_committee.runs.manifest import RunStatus, load_manifest, write_manifest
from model_committee.runs.review import write_review


def run_work_select(run_dir: Path) -> None:
    manifest = load_manifest(run_dir)
    score = ScoreResult.model_validate_json(
        (run_dir / "parsed" / "score_result.json").read_text(encoding="utf-8")
    )
    proposals = {
        proposal.proposal_id: proposal
        for proposal in [
            WorkProposal.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted((run_dir / "parsed").glob("*_proposal.json"))
        ]
    }
    validations = {
        item["proposal_id"]: PatchValidationResult.model_validate(item)
        for item in json.loads(
            (run_dir / "parsed" / "patch_validation_results.json").read_text(encoding="utf-8")
        )
    }
    if score.selected_proposal_id not in proposals:
        raise SelectionError("selected proposal does not exist")
    proposal = proposals[score.selected_proposal_id]
    validation = validations.get(score.selected_proposal_id)
    if validation is None or not (validation.patch_applies and validation.allowlist_passed):
        (run_dir / "review.md").write_text(
            "# Model-Committee Review\n\nSelected proposal failed mechanical validation.\n",
            encoding="utf-8",
        )
        raise SelectionError("selected proposal failed mechanical validation")
    (run_dir / "patches" / "selected.patch").write_text(proposal.patch, encoding="utf-8")
    (run_dir / "commit_message.txt").write_text(proposal.commit_message, encoding="utf-8")
    write_review(run_dir, manifest, proposal, score, validation)
    manifest.status = RunStatus.SELECTED
    manifest.phase = "work-select"
    write_manifest(run_dir, manifest)
