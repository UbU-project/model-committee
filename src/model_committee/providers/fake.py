import json
import re
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

    def response_path(self, run_dir: Path, prompt_path: Path) -> Path:
        return run_dir / "responses" / f"{prompt_path.stem}_response.json"

    def score_work_proposals(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> ScoreResult:
        del schema_path
        return _fake_score_result(self.provider_id, self.fixture_dir, run_dir, prompt_path)


class FakeClaudeCodeProvider:
    provider_id = "claude"

    def __init__(self, fixture_dir: Path):
        self.fixture_dir = fixture_dir

    def generate_work_proposal(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> WorkProposal:
        del prompt_path, schema_path
        src = self.fixture_dir / "claude_work_response.valid.json"
        dst = run_dir / "responses" / "claude_work_response.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return WorkProposal.model_validate_json(dst.read_text(encoding="utf-8"))

    def response_path(self, run_dir: Path, prompt_path: Path) -> Path:
        return run_dir / "responses" / f"{prompt_path.stem}_response.json"

    def score_work_proposals(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> ScoreResult:
        del schema_path
        return _fake_score_result(self.provider_id, self.fixture_dir, run_dir, prompt_path)


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


def _fake_score_result(
    scorer_provider: str, fixture_dir: Path, run_dir: Path, prompt_path: Path
) -> ScoreResult:
    prompt = prompt_path.read_text(encoding="utf-8")
    proposals = _candidate_proposals_from_prompt(prompt)
    if not proposals:
        src = fixture_dir / "codex_score_response.valid.json"
        result = ScoreResult.model_validate_json(src.read_text(encoding="utf-8"))
    else:
        scores = []
        for proposal in proposals:
            author = proposal["provider_id"]
            if scorer_provider == "claude" and author == "codex":
                score = 93
            elif scorer_provider == "codex" and author == "claude":
                score = 92
            elif scorer_provider == author:
                score = 99
            else:
                score = 88
            scores.append(
                {
                    "proposal_id": proposal["proposal_id"],
                    "score": score,
                    "patch_applies": True,
                    "implements_selected_work": True,
                    "preserves_question_schema": True,
                    "avoids_unnecessary_scope": True,
                    "decomposition_quality": "not_applicable",
                    "risks": [],
                    "required_fixes": [],
                    "rationale": f"Fake {scorer_provider} score for {proposal['proposal_id']}.",
                }
            )
        selected = max(scores, key=lambda item: item["score"])
        result = ScoreResult.model_validate(
            {
                "scores": scores,
                "selected_proposal_id": selected["proposal_id"],
                "selection_rationale": "Deterministic fake cross-score.",
            }
        )
    dst = run_dir / "responses" / f"{prompt_path.stem}_response.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8")
    return result


def _candidate_proposals_from_prompt(prompt: str) -> list[dict]:
    match = re.search(
        r"## Candidate proposals\s+```json\s+(?P<json>.*?)\s+```",
        prompt,
        flags=re.DOTALL,
    )
    if not match:
        return []
    data = json.loads(match.group("json"))
    return data if isinstance(data, list) else []
