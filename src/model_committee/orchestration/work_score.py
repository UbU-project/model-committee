import json
from pathlib import Path

from model_committee.config import ModelCommitteeConfig
from model_committee.markdown.questions_parser import parse_questions_file
from model_committee.providers.codex import CodexProvider
from model_committee.providers.fake import FakeCodexProvider
from model_committee.prompts.score_prompt import render_score_prompt
from model_committee.runs.manifest import RunStatus, load_manifest, write_manifest


def run_work_score(run_dir: Path, config: ModelCommitteeConfig, fake_providers: bool) -> None:
    manifest = load_manifest(run_dir)
    repo = Path(manifest.repo_path)
    question = {
        item.question_id: item for item in parse_questions_file(repo / "OPEN_QUESTIONS.md")
    }[manifest.selected_question_id]
    proposals = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_dir / "parsed").glob("*_proposal.json"))
    ]
    validations_path = run_dir / "parsed" / "patch_validation_results.json"
    validations = json.loads(validations_path.read_text(encoding="utf-8"))
    prompt, _warn = render_score_prompt(question, manifest.base_commit, proposals, validations)
    prompt_path = run_dir / "prompts" / "codex_score_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    provider = (
        FakeCodexProvider(Path("tests/fixtures/fake_responses"))
        if fake_providers
        else CodexProvider(config.codex, repo)
    )
    score = provider.score_work_proposals(
        run_dir, prompt_path, run_dir / "schemas" / "score_result.schema.json"
    )
    (run_dir / "parsed" / "score_result.json").write_text(
        json.dumps(score.model_dump(), indent=2) + "\n", encoding="utf-8"
    )
    manifest.status = RunStatus.SCORED
    manifest.phase = "work-score"
    write_manifest(run_dir, manifest)
