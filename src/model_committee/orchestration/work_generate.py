import json
from pathlib import Path

from model_committee.config import ModelCommitteeConfig
from model_committee.consistency.checker import check_repo
from model_committee.errors import (
    ConsistencyError,
    ModelOutputError,
    PatchValidationError,
    ProviderError,
)
from model_committee.markdown.questions_parser import parse_questions_file
from model_committee.patches.validate import validate_patch
from model_committee.providers.claude import ClaudeCodeProvider
from model_committee.providers.codex import CodexProvider
from model_committee.providers.fake import (
    FakeClaudeCodeProvider,
    FakeCodexProvider,
    FakeOllamaProvider,
    write_parsed_json,
)
from model_committee.providers.ollama import OllamaWorkProvider
from model_committee.prompts.work_prompt import render_work_prompt
from model_committee.ranking.answerability import compute_answerability, is_work_eligible
from model_committee.responses.schema_files import copy_schema_files_to_run
from model_committee.runs.layout import create_run_dir
from model_committee.runs.manifest import (
    RunStatus,
    append_provider_attempt,
    append_provider_failure,
    append_provider_success,
    write_manifest,
)


def _provider_model_name(provider) -> str | None:
    if hasattr(provider, "model_config"):
        return getattr(provider.model_config, "name", None)
    if hasattr(provider, "config"):
        return getattr(provider.config, "model", None)
    return None


def run_work_generate(
    repo: Path,
    question_id: str,
    config: ModelCommitteeConfig,
    config_path: Path | None,
    runs_dir: Path,
    fake_providers: bool,
    command: str,
) -> Path:
    report = check_repo(repo)
    if report.hard_failures:
        raise ConsistencyError("hard consistency failure")
    questions = parse_questions_file(repo / "OPEN_QUESTIONS.md")
    by_id = {question.question_id: question for question in questions}
    if question_id not in by_id:
        raise ConsistencyError(f"unknown question: {question_id}")
    answerability = compute_answerability(by_id[question_id], by_id)
    if not is_work_eligible(answerability):
        raise ConsistencyError(f"selected question blocked: {question_id}")

    run_dir, manifest = create_run_dir(runs_dir, repo, question_id, config_path, command)
    schemas = copy_schema_files_to_run(run_dir)
    prompt, _warn = render_work_prompt(repo, by_id[question_id], manifest.base_commit)
    codex_prompt = run_dir / "prompts" / "codex_work_prompt.md"
    claude_prompt = run_dir / "prompts" / "claude_work_prompt.md"
    ollama_prompt = run_dir / "prompts" / "ollama_work_prompt.md"
    codex_prompt.write_text(prompt, encoding="utf-8")
    claude_prompt.write_text(prompt, encoding="utf-8")
    ollama_prompt.write_text(prompt, encoding="utf-8")

    providers = []
    if fake_providers:
        fixture_dir = Path("tests/fixtures/fake_responses")
        providers = [
            FakeCodexProvider(fixture_dir),
            FakeClaudeCodeProvider(fixture_dir),
            FakeOllamaProvider(fixture_dir),
        ]
    else:
        if config.codex.enabled:
            providers.append(CodexProvider(config.codex, repo))
        if config.claude.enabled and not config.claude.score_only:
            providers.append(ClaudeCodeProvider(config.claude, repo))
        for model in sorted(
            [model for model in config.ollama.models if model.enabled],
            key=lambda item: item.priority,
        ):
            providers.append(OllamaWorkProvider(config.ollama, model))

    valid_count = 0
    validation_results = []
    for provider in providers:
        append_provider_attempt(
            manifest,
            provider_id=provider.provider_id,
            model_name=_provider_model_name(provider),
            phase="work-generate",
        )
        try:
            prompt_path = _work_prompt_for_provider(
                provider.provider_id,
                codex_prompt=codex_prompt,
                claude_prompt=claude_prompt,
                ollama_prompt=ollama_prompt,
            )
            proposal = provider.generate_work_proposal(
                run_dir, prompt_path, schemas.work_proposal_schema
            )
            parsed_name, patch_name = _work_artifact_names(provider.provider_id)
            validation = validate_patch(repo, proposal.proposal_id, proposal.patch)
            if validation.normalized_patch is not None:
                validation_notes = list(proposal.validation_notes)
                for warning in validation.warnings:
                    if warning not in validation_notes:
                        validation_notes.append(warning)
                proposal = proposal.model_copy(
                    update={
                        "changed_files": validation.changed_files,
                        "patch": validation.normalized_patch,
                        "validation_notes": validation_notes,
                    }
                )
            parsed_path = run_dir / "parsed" / parsed_name
            write_parsed_json(parsed_path, proposal)
            (run_dir / "patches" / patch_name).write_text(proposal.patch, encoding="utf-8")
            validation_results.append(validation.model_dump())
            if validation.patch_applies and validation.allowlist_passed:
                valid_count += 1
            append_provider_success(
                manifest,
                provider_id=provider.provider_id,
                model_name=_provider_model_name(provider),
                phase="work-generate",
                parsed_path=str(parsed_path),
            )
        except (ProviderError, ModelOutputError, PatchValidationError, ValueError, OSError) as exc:
            append_provider_failure(
                manifest,
                provider_id=provider.provider_id,
                model_name=_provider_model_name(provider),
                phase="work-generate",
                exc=exc,
                quorum_met=valid_count > 0,
            )
    for failure in manifest.provider_failures:
        failure.quorum_met = valid_count > 0
    (run_dir / "parsed" / "patch_validation_results.json").write_text(
        json.dumps(validation_results, indent=2) + "\n", encoding="utf-8"
    )
    if valid_count == 0:
        manifest.status = RunStatus.FAILED
        write_manifest(run_dir, manifest)
        raise PatchValidationError("no valid patch proposals")
    manifest.status = RunStatus.WAITING_FOR_SCORE
    write_manifest(run_dir, manifest)
    return run_dir


def _work_prompt_for_provider(
    provider_id: str,
    *,
    codex_prompt: Path,
    claude_prompt: Path,
    ollama_prompt: Path,
) -> Path:
    if provider_id == "codex":
        return codex_prompt
    if provider_id == "claude":
        return claude_prompt
    if provider_id.startswith("ollama:"):
        return ollama_prompt
    return codex_prompt


def _work_artifact_names(provider_id: str) -> tuple[str, str]:
    if provider_id == "codex":
        return "codex_work_proposal.json", "codex.patch"
    if provider_id == "claude":
        return "claude_work_proposal.json", "claude.patch"
    if provider_id.startswith("ollama:"):
        safe_name = provider_id.removeprefix("ollama:")
        return f"ollama_{safe_name}_proposal.json", f"ollama_{safe_name}.patch"
    safe_id = provider_id.replace(":", "_")
    return f"{safe_id}_work_proposal.json", f"{safe_id}.patch"
