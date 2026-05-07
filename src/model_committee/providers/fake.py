import json
from pathlib import Path

from model_committee.responses.json_extract import extract_json_object
from model_committee.responses.schemas import ScoreResult, WorkProposal


class FakeCodexProvider:
    provider_id = "codex"

    def __init__(self, fixture_dir: Path):
        self.fixture_dir = fixture_dir

    def generate_work_proposal(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> WorkProposal:
        del prompt_path, schema_path
        src = self.fixture_dir / "codex_work_response.valid.json"
        dst = run_dir / "responses" / "codex_work_response.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return WorkProposal.model_validate_json(dst.read_text(encoding="utf-8"))

    def score_work_proposals(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> ScoreResult:
        del prompt_path, schema_path
        src = self.fixture_dir / "codex_score_response.valid.json"
        dst = run_dir / "responses" / "codex_score_response.json"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return ScoreResult.model_validate_json(dst.read_text(encoding="utf-8"))


class FakeOllamaProvider:
    def __init__(self, fixture_dir: Path):
        self.fixture_dir = fixture_dir
        self.safe_name = "fake_model"
        self.provider_id = "ollama:fake_model"

    def generate_work_proposal(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> WorkProposal:
        del prompt_path, schema_path
        text = (self.fixture_dir / "ollama_response.valid.txt").read_text(encoding="utf-8")
        dst = run_dir / "responses" / "ollama_fake_model_response.txt"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")
        data = extract_json_object(text)
        return WorkProposal.model_validate(data)


def write_parsed_json(path: Path, model) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.model_dump(), indent=2) + "\n", encoding="utf-8")
