import json
import re
from pathlib import Path

from model_committee.config import ModelCommitteeConfig
from model_committee.errors import ModelOutputError, ProviderError
from model_committee.markdown.questions_parser import parse_questions_file
from model_committee.patches.validate import PatchValidationResult
from model_committee.providers.claude import ClaudeCodeProvider
from model_committee.providers.codex import CodexProvider
from model_committee.providers.fake import FakeClaudeCodeProvider, FakeCodexProvider
from model_committee.prompts.score_prompt import render_score_prompt
from model_committee.responses.schemas import (
    ProposalScore,
    SchemaValidationStatus,
    ScoreMatrixRow,
    ScoreResult,
    WorkProposal,
)
from model_committee.runs.manifest import (
    RunStatus,
    append_provider_attempt,
    append_provider_failure,
    append_provider_success,
    load_manifest,
    write_manifest,
)

from .quorum import evaluate_quorum


def run_work_score(run_dir: Path, config: ModelCommitteeConfig, fake_providers: bool) -> None:
    manifest = load_manifest(run_dir)
    repo = Path(manifest.repo_path)
    question = {
        item.question_id: item for item in parse_questions_file(repo / "OPEN_QUESTIONS.md")
    }[manifest.selected_question_id]
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
    valid_proposals = [
        proposal
        for proposal in proposals.values()
        if _proposal_is_mechanically_valid(proposal, validations)
    ]
    scoring_providers = _scoring_providers(config, repo, fake_providers)
    score_matrix: list[ScoreMatrixRow] = []

    for proposal in sorted(valid_proposals, key=lambda item: item.proposal_id):
        for provider in scoring_providers:
            if provider.provider_id == proposal.provider_id:
                continue
            prompt_path = (
                run_dir
                / "prompts"
                / (
                    f"{_safe_artifact_name(provider.provider_id)}_score_"
                    f"{_safe_artifact_name(proposal.proposal_id)}.md"
                )
            )
            prompt, _warn = render_score_prompt(
                question,
                manifest.base_commit,
                [proposal.model_dump()],
                [validations[proposal.proposal_id].model_dump()],
                scoring_provider_id=provider.provider_id,
                author_provider_id=proposal.provider_id,
            )
            prompt_path.write_text(prompt, encoding="utf-8")
            append_provider_attempt(
                manifest,
                provider_id=provider.provider_id,
                model_name=_provider_model_name(provider),
                phase="work-score",
                target_proposal_id=proposal.proposal_id,
                response_path=str(
                    provider.response_path(run_dir, prompt_path)
                ),
            )
            try:
                score_result = provider.score_work_proposals(
                    run_dir, prompt_path, run_dir / "schemas" / "score_result.schema.json"
                )
                score = _score_for_proposal(score_result, proposal.proposal_id)
                parsed_path = run_dir / "parsed" / f"{prompt_path.stem}_result.json"
                parsed_path.write_text(
                    json.dumps(score_result.model_dump(), indent=2) + "\n",
                    encoding="utf-8",
                )
                score_matrix.append(
                    ScoreMatrixRow(
                        proposal_id=proposal.proposal_id,
                        author_provider=proposal.provider_id,
                        scorer_provider=provider.provider_id,
                        score=score.score,
                        valid=True,
                        rationale=score.rationale,
                        implements_selected_work=score.implements_selected_work,
                        avoids_unnecessary_scope=score.avoids_unnecessary_scope,
                        required_fixes=score.required_fixes,
                        risks=score.risks,
                        schema_validation=SchemaValidationStatus(
                            valid=True,
                            response_path=str(
                                provider.response_path(run_dir, prompt_path)
                            ),
                        ),
                    )
                )
                append_provider_success(
                    manifest,
                    provider_id=provider.provider_id,
                    model_name=_provider_model_name(provider),
                    phase="work-score",
                    target_proposal_id=proposal.proposal_id,
                    response_path=str(
                        provider.response_path(run_dir, prompt_path)
                    ),
                    parsed_path=str(parsed_path),
                )
            except (ProviderError, ModelOutputError, ValueError, OSError) as exc:
                score_matrix.append(
                    ScoreMatrixRow(
                        proposal_id=proposal.proposal_id,
                        author_provider=proposal.provider_id,
                        scorer_provider=provider.provider_id,
                        score=None,
                        valid=False,
                        rationale="",
                        required_fixes=[],
                        risks=[],
                        schema_validation=SchemaValidationStatus(
                            valid=False,
                            message=str(exc),
                            response_path=getattr(exc, "response_path", None),
                            stderr_path=getattr(exc, "stderr_path", None),
                        ),
                    )
                )
                append_provider_failure(
                    manifest,
                    provider_id=provider.provider_id,
                    model_name=_provider_model_name(provider),
                    phase="work-score",
                    exc=exc,
                    quorum_met=False,
                )

    aggregates, disagreement_flags, quorum = evaluate_quorum(
        proposals=proposals,
        validations=validations,
        score_matrix=score_matrix,
    )
    (run_dir / "parsed" / "score_matrix.json").write_text(
        json.dumps([row.model_dump(mode="json") for row in score_matrix], indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "parsed" / "score_aggregates.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in aggregates], indent=2) + "\n",
        encoding="utf-8",
    )
    _write_aggregate_score_result(run_dir, proposals, validations, aggregates, score_matrix, quorum)

    selected_aggregate = next(
        (item for item in aggregates if item.proposal_id == quorum.selected_proposal_id),
        None,
    )
    manifest.score_matrix = score_matrix
    manifest.score_aggregates = aggregates
    manifest.cross_score_count = sum(
        1
        for row in score_matrix
        if row.valid and row.score is not None and row.scorer_provider != row.author_provider
    )
    manifest.score_mean = selected_aggregate.score_mean if selected_aggregate else None
    manifest.score_spread = selected_aggregate.score_spread if selected_aggregate else None
    manifest.frontier_score_gap = (
        selected_aggregate.frontier_score_gap if selected_aggregate else None
    )
    manifest.disagreement_flags = disagreement_flags
    manifest.quorum_result = quorum
    manifest.selected_proposal_id = quorum.selected_proposal_id
    manifest.human_review_required = quorum.human_review_required
    manifest.automated_selection_valid = quorum.valid
    manifest.status = RunStatus.SCORED
    manifest.phase = "work-score"
    write_manifest(run_dir, manifest)


def _proposal_is_mechanically_valid(
    proposal: WorkProposal, validations: dict[str, PatchValidationResult]
) -> bool:
    validation = validations.get(proposal.proposal_id)
    return bool(validation and validation.patch_applies and validation.allowlist_passed)


def _scoring_providers(config: ModelCommitteeConfig, repo: Path, fake_providers: bool):
    if fake_providers:
        fixture_dir = Path("tests/fixtures/fake_responses")
        return [FakeCodexProvider(fixture_dir), FakeClaudeCodeProvider(fixture_dir)]
    providers = []
    if config.codex.enabled:
        providers.append(CodexProvider(config.codex, repo))
    if config.claude.enabled:
        providers.append(ClaudeCodeProvider(config.claude, repo))
    return providers


def _provider_model_name(provider) -> str | None:
    if hasattr(provider, "config"):
        return getattr(provider.config, "model", None)
    return None


def _score_for_proposal(score_result: ScoreResult, proposal_id: str) -> ProposalScore:
    for score in score_result.scores:
        if score.proposal_id == proposal_id:
            return score
    raise ModelOutputError(f"score result missing proposal_id {proposal_id}")


def _safe_artifact_name(value: str) -> str:
    # Two distinct provider IDs could theoretically map to the same safe name,
    # but this is acceptable for the current provider set (codex, claude, ollama:*).
    safe = value.lower().replace("/", "__").replace(":", "--").replace(" ", "_")
    return re.sub(r"[^a-z0-9_.-]", "", safe)


def _write_aggregate_score_result(
    run_dir: Path,
    proposals: dict[str, WorkProposal],
    validations: dict[str, PatchValidationResult],
    aggregates,
    score_matrix: list[ScoreMatrixRow],
    quorum,
) -> None:
    if quorum.selected_proposal_id is None:
        return
    scores = []
    for aggregate in aggregates:
        validation = validations[aggregate.proposal_id]
        rows = [row for row in score_matrix if row.proposal_id == aggregate.proposal_id]
        valid_rows = [row for row in rows if row.valid]
        risks = sorted({risk for row in rows for risk in row.risks})
        required_fixes = sorted({fix for row in rows for fix in row.required_fixes})
        scores.append(
            ProposalScore(
                proposal_id=aggregate.proposal_id,
                score=int(round(aggregate.score_mean or 0)),
                patch_applies=validation.patch_applies,
                implements_selected_work=all(
                    row.implements_selected_work for row in valid_rows
                )
                if valid_rows
                else True,
                preserves_question_schema=not proposals[aggregate.proposal_id].validation_notes,
                avoids_unnecessary_scope=all(
                    row.avoids_unnecessary_scope for row in valid_rows
                )
                if valid_rows
                else True,
                decomposition_quality="not_applicable",
                risks=risks,
                required_fixes=required_fixes,
                rationale=(
                    f"Aggregate cross-score mean from {aggregate.cross_score_count} "
                    "valid scorer(s)."
                ),
            )
        )
    score_result = ScoreResult(
        scores=scores,
        selected_proposal_id=quorum.selected_proposal_id,
        selection_rationale="Selected by local v0.2 quorum policy from cross-scores.",
    )
    (run_dir / "parsed" / "score_result.json").write_text(
        json.dumps(score_result.model_dump(), indent=2) + "\n",
        encoding="utf-8",
    )
