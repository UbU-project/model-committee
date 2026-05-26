import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from model_committee.responses.schemas import (
    DisagreementFlag,
    ProposalScoreAggregate,
    QuorumResult,
    ScoreMatrixRow,
)


class RunStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_SCORE = "waiting_for_score"
    SCORED = "scored"
    SELECTED = "selected"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    FAILED = "failed"


class ProviderFailureEvent(BaseModel):
    provider_id: str
    model_name: str | None = None
    phase: str
    failure_class: str
    message: str
    timeout_seconds: int | None = None
    exit_status: int | None = None
    stderr_path: str | None = None
    response_path: str | None = None
    quorum_met: bool | None = None


class ProviderAttemptEvent(BaseModel):
    provider_id: str
    model_name: str | None = None
    phase: str
    target_proposal_id: str | None = None
    response_path: str | None = None
    stderr_path: str | None = None


class ProviderSuccessEvent(BaseModel):
    provider_id: str
    model_name: str | None = None
    phase: str
    target_proposal_id: str | None = None
    response_path: str | None = None
    parsed_path: str | None = None


class RunManifest(BaseModel):
    schema_version: str = "0.3"
    run_id: str
    created_at_utc: str
    repo_path: str
    base_commit: str
    selected_question_id: str
    phase: str
    config_path: str | None = None
    status: RunStatus
    commands: list[str] = Field(default_factory=list)
    providers_attempted: list[str] = Field(default_factory=list)
    providers_succeeded: list[str] = Field(default_factory=list)
    providers_failed: list[str] = Field(default_factory=list)
    provider_attempts: list[ProviderAttemptEvent] = Field(default_factory=list)
    provider_successes: list[ProviderSuccessEvent] = Field(default_factory=list)
    provider_failures: list[ProviderFailureEvent] = Field(default_factory=list)
    score_matrix: list[ScoreMatrixRow] = Field(default_factory=list)
    score_aggregates: list[ProposalScoreAggregate] = Field(default_factory=list)
    cross_score_count: int = 0
    score_mean: float | None = None
    score_spread: int | None = None
    frontier_score_gap: int | None = None
    disagreement_flags: list[DisagreementFlag] = Field(default_factory=list)
    quorum_result: QuorumResult | None = None
    selected_proposal_id: str | None = None
    automated_selection_valid: bool = False
    human_review_required: bool = False
    artifact_publication_status: str = "not_applicable"
    prompt_size_warning: bool = False


def utc_now_text() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_manifest(run_dir: Path, manifest: RunManifest) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )


def load_manifest(run_dir: Path) -> RunManifest:
    return RunManifest.model_validate_json((run_dir / "manifest.json").read_text(encoding="utf-8"))


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def append_provider_attempt(
    manifest: RunManifest,
    *,
    provider_id: str,
    model_name: str | None,
    phase: str,
    target_proposal_id: str | None = None,
    response_path: str | None = None,
    stderr_path: str | None = None,
) -> None:
    _append_unique(manifest.providers_attempted, provider_id)
    manifest.provider_attempts.append(
        ProviderAttemptEvent(
            provider_id=provider_id,
            model_name=model_name,
            phase=phase,
            target_proposal_id=target_proposal_id,
            response_path=response_path,
            stderr_path=stderr_path,
        )
    )


def append_provider_success(
    manifest: RunManifest,
    *,
    provider_id: str,
    model_name: str | None,
    phase: str,
    target_proposal_id: str | None = None,
    response_path: str | None = None,
    parsed_path: str | None = None,
) -> None:
    _append_unique(manifest.providers_succeeded, provider_id)
    manifest.provider_successes.append(
        ProviderSuccessEvent(
            provider_id=provider_id,
            model_name=model_name,
            phase=phase,
            target_proposal_id=target_proposal_id,
            response_path=response_path,
            parsed_path=parsed_path,
        )
    )


def append_provider_failure(
    manifest: RunManifest,
    *,
    provider_id: str,
    model_name: str | None,
    phase: str,
    exc: Exception,
    quorum_met: bool | None,
) -> None:
    event = ProviderFailureEvent(
        provider_id=provider_id,
        model_name=model_name,
        phase=phase,
        failure_class=exc.__class__.__name__,
        message=str(exc),
        timeout_seconds=getattr(exc, "timeout_seconds", None),
        exit_status=getattr(exc, "exit_status", None),
        stderr_path=getattr(exc, "stderr_path", None),
        response_path=getattr(exc, "response_path", None),
        quorum_met=quorum_met,
    )
    manifest.provider_failures.append(event)
    manifest.providers_failed.append(f"{provider_id}: {event.failure_class}: {event.message}")
