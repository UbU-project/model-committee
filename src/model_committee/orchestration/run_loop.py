from collections.abc import Collection
from pathlib import Path

from model_committee.config import ModelCommitteeConfig
from model_committee.orchestration.rank import run_rank
from model_committee.orchestration.work_generate import run_work_generate
from model_committee.orchestration.work_score import run_work_score
from model_committee.orchestration.work_select import run_work_select
from model_committee.ranking.answerability import is_work_eligible


def run_loop(
    repo: Path,
    config: ModelCommitteeConfig,
    config_path: Path | None,
    runs_dir: Path,
    fake_providers: bool = False,
    phase_filter: str | None = None,
    *,
    worked_question_ids: Collection[str] = (),
) -> Path:
    ranking = run_rank(repo, phase_filter=phase_filter)
    if not ranking.selected_question_id:
        raise RuntimeError("no eligible question")
    # Prefer questions not yet worked in this pass. When the pass is exhausted,
    # revisit the highest-ranked question that remains eligible.
    question_id = next(
        (
            question.question_id
            for question in ranking.ranked_questions
            if is_work_eligible(question.answerability_score)
            and question.question_id not in worked_question_ids
        ),
        ranking.selected_question_id,
    )
    run_dir = run_work_generate(
        repo,
        question_id,
        config,
        config_path,
        runs_dir,
        fake_providers,
        "model-committee run-loop",
    )
    run_work_score(run_dir, config, fake_providers)
    run_work_select(run_dir)
    return run_dir
