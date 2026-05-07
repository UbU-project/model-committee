from pathlib import Path
from typing import Protocol

from model_committee.responses.schemas import ScoreResult, WorkProposal


class WorkProvider(Protocol):
    provider_id: str

    def generate_work_proposal(
        self,
        run_dir: Path,
        prompt_path: Path,
        schema_path: Path,
    ) -> WorkProposal: ...


class ScoreProvider(Protocol):
    provider_id: str

    def score_work_proposals(
        self,
        run_dir: Path,
        prompt_path: Path,
        schema_path: Path,
    ) -> ScoreResult: ...
