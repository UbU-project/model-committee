from model_committee.orchestration.quorum import evaluate_quorum
from model_committee.patches.validate import PatchValidationResult
from model_committee.responses.schemas import (
    SchemaValidationStatus,
    ScoreMatrixRow,
    WorkProposal,
)


def _proposal(proposal_id="codex-work-001", provider_id="codex") -> WorkProposal:
    return WorkProposal(
        proposal_id=proposal_id,
        provider_id=provider_id,
        model_name=f"{provider_id}:model",
        question_id="UBU-Q0001",
        base_commit="unknown",
        summary="summary",
        rationale="rationale",
        changed_files=["DESIGN.md"],
        patch="diff --git a/DESIGN.md b/DESIGN.md\n",
        commit_message="message",
        validation_notes=[],
        new_questions_added=[],
        questions_resolved=[],
        decisions_added=[],
        requires_human_review=False,
    )


def _validation(proposal_id: str) -> PatchValidationResult:
    return PatchValidationResult(
        proposal_id=proposal_id,
        patch_applies=True,
        allowlist_passed=True,
        changed_files=["DESIGN.md"],
    )


def _row(
    proposal_id: str,
    author: str,
    scorer: str,
    score: int,
    self_score: bool = False,
) -> ScoreMatrixRow:
    return ScoreMatrixRow(
        proposal_id=proposal_id,
        author_provider=author,
        scorer_provider=scorer,
        score=score,
        valid=True,
        rationale="rationale",
        required_fixes=[],
        risks=[],
        schema_validation=SchemaValidationStatus(valid=True),
        diagnostic_self_score=self_score,
    )


def test_cross_scoring_excludes_self_score_from_quorum():
    proposal = _proposal()
    aggregates, flags, quorum = evaluate_quorum(
        proposals={proposal.proposal_id: proposal},
        validations={proposal.proposal_id: _validation(proposal.proposal_id)},
        score_matrix=[
            _row("codex-work-001", "codex", "codex", 100, self_score=True),
        ],
    )
    assert aggregates[0].cross_score_count == 0
    assert quorum.valid is False
    assert quorum.human_review_required is True
    assert any(flag.code == "NO_VALID_CROSS_SCORE" for flag in flags)


def test_quorum_passes_with_valid_cross_score_and_no_critical_disagreement():
    proposal = _proposal()
    aggregates, flags, quorum = evaluate_quorum(
        proposals={proposal.proposal_id: proposal},
        validations={proposal.proposal_id: _validation(proposal.proposal_id)},
        score_matrix=[
            _row("codex-work-001", "codex", "claude", 82),
        ],
    )
    assert aggregates[0].score_mean == 82
    assert flags == []
    assert quorum.valid is True
    assert quorum.selected_proposal_id == "codex-work-001"


def test_quorum_fails_with_no_cross_score():
    proposal = _proposal()
    _aggregates, flags, quorum = evaluate_quorum(
        proposals={proposal.proposal_id: proposal},
        validations={proposal.proposal_id: _validation(proposal.proposal_id)},
        score_matrix=[],
    )
    assert quorum.valid is False
    assert "no valid cross-score" in "; ".join(quorum.blocked_reasons)
    assert any(flag.severity == "critical" for flag in flags)


def test_quorum_flags_human_review_on_frontier_score_gap():
    proposal = _proposal("ollama-work-001", "ollama:fake")
    _aggregates, flags, quorum = evaluate_quorum(
        proposals={proposal.proposal_id: proposal},
        validations={proposal.proposal_id: _validation(proposal.proposal_id)},
        score_matrix=[
            _row("ollama-work-001", "ollama:fake", "codex", 95),
            _row("ollama-work-001", "ollama:fake", "claude", 60),
        ],
    )
    assert quorum.valid is False
    assert quorum.human_review_required is True
    assert any(flag.code == "FRONTIER_SCORE_GAP" for flag in flags)
