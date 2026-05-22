import json
from pathlib import Path

from model_committee.errors import HumanReviewRequired, SelectionError
from model_committee.patches.validate import PatchValidationResult
from model_committee.responses.schemas import ScoreMatrixRow, WorkProposal
from model_committee.runs.manifest import RunStatus, load_manifest, write_manifest
from model_committee.runs.review import write_review

from .quorum import evaluate_quorum  # fallback when manifest has no stored quorum

COMMIT_MESSAGE_PREFIX = "UMC: "


def format_commit_message(commit_message: str) -> str:
    if commit_message.startswith(COMMIT_MESSAGE_PREFIX):
        return commit_message
    return f"{COMMIT_MESSAGE_PREFIX}{commit_message}"


def run_work_select(run_dir: Path) -> None:
    manifest = load_manifest(run_dir)
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
    score_matrix = _load_score_matrix(run_dir, manifest)
    if manifest.quorum_result is not None and manifest.score_aggregates:
        quorum = manifest.quorum_result
        aggregates = manifest.score_aggregates
        disagreement_flags = manifest.disagreement_flags
    else:
        aggregates, disagreement_flags, quorum = evaluate_quorum(
            proposals=proposals,
            validations=validations,
            score_matrix=score_matrix,
        )
    selected_id = quorum.selected_proposal_id
    manifest.score_matrix = score_matrix
    manifest.score_aggregates = aggregates
    manifest.cross_score_count = sum(
        1
        for row in score_matrix
        if row.valid and row.score is not None and row.scorer_provider != row.author_provider
    )
    manifest.disagreement_flags = disagreement_flags
    manifest.quorum_result = quorum
    manifest.selected_proposal_id = selected_id
    manifest.human_review_required = quorum.human_review_required
    manifest.automated_selection_valid = quorum.valid
    manifest.artifact_publication_status = "operator_pending"
    selected_aggregate = next(
        (item for item in aggregates if item.proposal_id == selected_id),
        None,
    )
    manifest.score_mean = selected_aggregate.score_mean if selected_aggregate else None
    manifest.score_spread = selected_aggregate.score_spread if selected_aggregate else None
    manifest.frontier_score_gap = (
        selected_aggregate.frontier_score_gap if selected_aggregate else None
    )

    if selected_id is None:
        manifest.status = RunStatus.HUMAN_REVIEW_REQUIRED
        manifest.phase = "work-select"
        write_review(run_dir, manifest, proposals, validations)
        write_manifest(run_dir, manifest)
        raise HumanReviewRequired("; ".join(quorum.blocked_reasons))
    if selected_id not in proposals:
        raise SelectionError("selected proposal does not exist")
    proposal = proposals[selected_id]
    validation = validations.get(selected_id)
    if validation is None or not (validation.patch_applies and validation.allowlist_passed):
        manifest.status = RunStatus.HUMAN_REVIEW_REQUIRED
        manifest.phase = "work-select"
        manifest.human_review_required = True
        manifest.automated_selection_valid = False
        write_review(run_dir, manifest, proposals, validations)
        write_manifest(run_dir, manifest)
        raise HumanReviewRequired("selected proposal failed mechanical validation")
    if not quorum.valid:
        manifest.status = RunStatus.HUMAN_REVIEW_REQUIRED
        manifest.phase = "work-select"
        write_review(run_dir, manifest, proposals, validations)
        write_manifest(run_dir, manifest)
        raise HumanReviewRequired("; ".join(quorum.blocked_reasons))

    selected_patch = validation.normalized_patch or proposal.patch
    (run_dir / "patches" / "selected.patch").write_text(selected_patch, encoding="utf-8")
    (run_dir / "commit_message.txt").write_text(
        format_commit_message(proposal.commit_message),
        encoding="utf-8",
    )
    manifest.status = RunStatus.SELECTED
    manifest.phase = "work-select"
    manifest.human_review_required = False
    manifest.automated_selection_valid = True
    write_review(run_dir, manifest, proposals, validations)
    write_manifest(run_dir, manifest)


def _load_score_matrix(run_dir: Path, manifest) -> list[ScoreMatrixRow]:
    matrix_path = run_dir / "parsed" / "score_matrix.json"
    if matrix_path.exists():
        return [
            ScoreMatrixRow.model_validate(item)
            for item in json.loads(matrix_path.read_text(encoding="utf-8"))
        ]
    return manifest.score_matrix
