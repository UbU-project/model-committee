import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_SCORE = "waiting_for_score"
    SCORED = "scored"
    SELECTED = "selected"
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


class RunManifest(BaseModel):
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
    provider_failures: list[ProviderFailureEvent] = Field(default_factory=list)


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
