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
from model_committee.providers.codex import CodexProvider
from model_committee.providers.fake import FakeCodexProvider, FakeOllamaProvider, write_parsed_json
from model_committee.providers.ollama import OllamaWorkProvider
from model_committee.prompts.work_prompt import render_work_prompt
from model_committee.ranking.answerability import compute_answerability, is_work_eligible
from model_committee.responses.schema_files import copy_schema_files_to_run
from model_committee.runs.layout import create_run_dir
from model_committee.runs.manifest import RunStatus, append_provider_failure, write_manifest


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
    ollama_prompt = run_dir / "prompts" / "ollama_work_prompt.md"
    codex_prompt.write_text(prompt, encoding="utf-8")
    ollama_prompt.write_text(prompt, encoding="utf-8")

    providers = []
    if fake_providers:
        fixture_dir = Path("tests/fixtures/fake_responses")
        providers = [FakeCodexProvider(fixture_dir), FakeOllamaProvider(fixture_dir)]
    else:
        if config.codex.enabled:
            providers.append(CodexProvider(config.codex, repo))
        for model in sorted(
            [model for model in config.ollama.models if model.enabled],
            key=lambda item: item.priority,
        ):
            providers.append(OllamaWorkProvider(config.ollama, model))

    valid_count = 0
    validation_results = []
    for provider in providers:
        manifest.providers_attempted.append(provider.provider_id)
        try:
            prompt_path = (
                ollama_prompt if provider.provider_id.startswith("ollama:") else codex_prompt
            )
            proposal = provider.generate_work_proposal(
                run_dir, prompt_path, schemas.work_proposal_schema
            )
            parsed_name = (
                "codex_work_proposal.json"
                if provider.provider_id == "codex"
                else f"ollama_{provider.provider_id.removeprefix('ollama:')}_proposal.json"
            )
            patch_name = (
                "codex.patch"
                if provider.provider_id == "codex"
                else f"ollama_{provider.provider_id.removeprefix('ollama:')}.patch"
            )
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
            write_parsed_json(run_dir / "parsed" / parsed_name, proposal)
            (run_dir / "patches" / patch_name).write_text(proposal.patch, encoding="utf-8")
            validation_results.append(validation.model_dump())
            if validation.patch_applies and validation.allowlist_passed:
                valid_count += 1
            manifest.providers_succeeded.append(provider.provider_id)
        except (ProviderError, ModelOutputError, PatchValidationError, ValueError, OSError) as exc:
            append_provider_failure(
                manifest,
                provider_id=provider.provider_id,
                model_name=_provider_model_name(provider),
                phase="work-generate",
                exc=exc,
                quorum_met=valid_count > 0,
            )
            if provider.provider_id == "codex":
                manifest.status = RunStatus.FAILED
                manifest.phase = "work-generate"
                for failure in manifest.provider_failures:
                    failure.quorum_met = valid_count > 0
                write_manifest(run_dir, manifest)
                raise
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
