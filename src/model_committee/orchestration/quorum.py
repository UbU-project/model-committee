from collections import defaultdict

from model_committee.patches.validate import PatchValidationResult
from model_committee.responses.schemas import (
    DisagreementFlag,
    ProposalScoreAggregate,
    QuorumResult,
    ScoreMatrixRow,
    WorkProposal,
)

FRONTIER_SCORE_GAP_CRITICAL = 25
MIN_SELECTED_SCORE = 70


def evaluate_quorum(
    *,
    proposals: dict[str, WorkProposal],
    validations: dict[str, PatchValidationResult],
    score_matrix: list[ScoreMatrixRow],
) -> tuple[list[ProposalScoreAggregate], list[DisagreementFlag], QuorumResult]:
    valid_work_proposal_ids = {
        proposal_id
        for proposal_id, validation in validations.items()
        if validation.patch_applies and validation.allowlist_passed and proposal_id in proposals
    }
    evidence_by_proposal: dict[str, list[ScoreMatrixRow]] = defaultdict(list)
    for row in score_matrix:
        if (
            row.valid
            and row.score is not None
            and row.proposal_id in valid_work_proposal_ids
            and row.scorer_provider != row.author_provider
            and not row.diagnostic_self_score
        ):
            evidence_by_proposal[row.proposal_id].append(row)

    aggregates: list[ProposalScoreAggregate] = []
    flags: list[DisagreementFlag] = []
    for proposal_id in sorted(valid_work_proposal_ids):
        proposal = proposals[proposal_id]
        rows = evidence_by_proposal.get(proposal_id, [])
        scores = [row.score for row in rows if row.score is not None]
        mean = round(sum(scores) / len(scores), 2) if scores else None
        spread = max(scores) - min(scores) if scores else None
        proposal_flags: list[DisagreementFlag] = []
        if spread is not None and spread >= FRONTIER_SCORE_GAP_CRITICAL:
            proposal_flags.append(
                DisagreementFlag(
                    code="FRONTIER_SCORE_GAP",
                    severity="critical",
                    proposal_id=proposal_id,
                    message=(f"frontier_score_gap {spread} is >= {FRONTIER_SCORE_GAP_CRITICAL}"),
                )
            )
        flags.extend(proposal_flags)
        aggregates.append(
            ProposalScoreAggregate(
                proposal_id=proposal_id,
                author_provider=proposal.provider_id,
                cross_score_count=len(scores),
                score_mean=mean,
                score_spread=spread,
                frontier_score_gap=spread,
                disagreement_flags=proposal_flags,
            )
        )

    blocked_reasons: list[str] = []
    selected = _select_aggregate(aggregates)
    if not valid_work_proposal_ids:
        blocked_reasons.append("no valid work proposal")
    if selected is None:
        blocked_reasons.append("no valid cross-score from a different frontier provider")
        no_cross_flag = DisagreementFlag(
            code="NO_VALID_CROSS_SCORE",
            severity="critical",
            proposal_id=None,
            message="no valid cross-score from a different frontier provider",
        )
        flags.append(no_cross_flag)
    else:
        if selected.score_mean is not None and selected.score_mean < MIN_SELECTED_SCORE:
            low_score_flag = DisagreementFlag(
                code="SELECTED_SCORE_BELOW_THRESHOLD",
                severity="warning",
                proposal_id=selected.proposal_id,
                message=f"selected_score {selected.score_mean} is < {MIN_SELECTED_SCORE}",
            )
            flags.append(low_score_flag)
            blocked_reasons.append("selected score below automated-selection threshold")
        if any(flag.severity == "critical" for flag in selected.disagreement_flags):
            blocked_reasons.append("critical disagreement flag on selected proposal")

    valid = selected is not None and not blocked_reasons
    quorum = QuorumResult(
        valid=valid,
        human_review_required=not valid,
        selected_proposal_id=selected.proposal_id if selected else None,
        selected_score=selected.score_mean if selected else None,
        selected_cross_score_count=selected.cross_score_count if selected else 0,
        blocked_reasons=blocked_reasons,
    )
    return aggregates, flags, quorum


def _select_aggregate(
    aggregates: list[ProposalScoreAggregate],
) -> ProposalScoreAggregate | None:
    eligible = [
        aggregate
        for aggregate in aggregates
        if aggregate.cross_score_count > 0 and aggregate.score_mean is not None
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda item: (
            item.score_mean or 0,
            item.cross_score_count,
            item.proposal_id,
        ),
    )
