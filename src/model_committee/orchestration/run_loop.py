from pathlib import Path

from model_committee.config import ModelCommitteeConfig
from model_committee.orchestration.rank import run_rank
from model_committee.orchestration.work_generate import run_work_generate
from model_committee.orchestration.work_score import run_work_score
from model_committee.orchestration.work_select import run_work_select


def run_loop(
    repo: Path,
    config: ModelCommitteeConfig,
    config_path: Path | None,
    runs_dir: Path,
    fake_providers: bool = False,
    phase_filter: str | None = None,
) -> Path:
    ranking = run_rank(repo, phase_filter=phase_filter)
    if not ranking.selected_question_id:
        raise RuntimeError("no eligible question")
    run_dir = run_work_generate(
        repo,
        ranking.selected_question_id,
        config,
        config_path,
        runs_dir,
        fake_providers,
        "model-committee run-loop",
    )
    run_work_score(run_dir, config, fake_providers)
    run_work_select(run_dir)
    return run_dir
