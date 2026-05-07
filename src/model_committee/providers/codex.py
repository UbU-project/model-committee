import json
import subprocess
from pathlib import Path

from model_committee.config import CodexConfig
from model_committee.errors import ProviderError
from model_committee.responses.schemas import ScoreResult, WorkProposal


class CodexProvider:
    provider_id = "codex"

    def __init__(self, config: CodexConfig, repo_path: Path):
        self.config = config
        self.repo_path = repo_path

    def _run(
        self,
        run_dir: Path,
        prompt_path: Path,
        schema_path: Path,
        output_path: Path,
        events_path: Path,
        stderr_path: Path,
    ) -> dict:
        args = [
            self.config.command,
            "exec",
            "--skip-git-repo-check",
            "--cd",
            str(self.repo_path),
            "--model",
            self.config.model,
            "--sandbox",
            self.config.sandbox,
            "--json",
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            "-",
        ]
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with (
            events_path.open("w", encoding="utf-8") as events,
            stderr_path.open("w", encoding="utf-8") as stderr,
        ):
            result = subprocess.run(
                args,
                input=prompt_path.read_text(encoding="utf-8"),
                text=True,
                stdout=events,
                stderr=stderr,
                timeout=self.config.timeout_seconds,
                check=False,
            )
        if result.returncode != 0:
            raise ProviderError(f"codex exited with {result.returncode}")
        if not output_path.exists():
            raise ProviderError(f"codex output missing: {output_path}")
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProviderError(f"codex output is not valid JSON: {exc}") from exc

    def generate_work_proposal(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> WorkProposal:
        data = self._run(
            run_dir,
            prompt_path,
            schema_path,
            run_dir / "responses" / "codex_work_response.json",
            run_dir / "responses" / "codex_work_events.jsonl",
            run_dir / "responses" / "codex_work_stderr.txt",
        )
        return WorkProposal.model_validate(data)

    def score_work_proposals(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> ScoreResult:
        data = self._run(
            run_dir,
            prompt_path,
            schema_path,
            run_dir / "responses" / "codex_score_response.json",
            run_dir / "responses" / "codex_score_events.jsonl",
            run_dir / "responses" / "codex_score_stderr.txt",
        )
        return ScoreResult.model_validate(data)
