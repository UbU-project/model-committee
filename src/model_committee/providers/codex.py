import json
import subprocess
from pathlib import Path

from pydantic import ValidationError

from model_committee.config import CodexConfig
from model_committee.errors import ModelOutputError, ProviderError
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
            try:
                result = subprocess.run(
                    args,
                    input=prompt_path.read_text(encoding="utf-8"),
                    text=True,
                    stdout=events,
                    stderr=stderr,
                    timeout=self.config.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ProviderError(
                    f"codex timed out after {self.config.timeout_seconds} seconds",
                    timeout_seconds=self.config.timeout_seconds,
                    stderr_path=str(stderr_path),
                    response_path=str(output_path),
                ) from exc
        if result.returncode != 0:
            raise ProviderError(
                f"codex exited with {result.returncode}",
                exit_status=result.returncode,
                stderr_path=str(stderr_path),
                response_path=str(output_path),
            )
        if not output_path.exists():
            raise ProviderError(
                f"codex output missing: {output_path}",
                stderr_path=str(stderr_path),
                response_path=str(output_path),
            )
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ModelOutputError(
                f"codex output is not valid JSON: {exc}",
                stderr_path=str(stderr_path),
                response_path=str(output_path),
            ) from exc

    def generate_work_proposal(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> WorkProposal:
        output_path = run_dir / "responses" / "codex_work_response.json"
        stderr_path = run_dir / "responses" / "codex_work_stderr.txt"
        data = self._run(
            run_dir,
            prompt_path,
            schema_path,
            output_path,
            run_dir / "responses" / "codex_work_events.jsonl",
            stderr_path,
        )
        try:
            return WorkProposal.model_validate(data)
        except ValidationError as exc:
            raise ModelOutputError(
                f"codex work proposal failed schema validation: {exc}",
                stderr_path=str(stderr_path),
                response_path=str(output_path),
            ) from exc

    def score_work_proposals(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> ScoreResult:
        output_path = run_dir / "responses" / "codex_score_response.json"
        stderr_path = run_dir / "responses" / "codex_score_stderr.txt"
        data = self._run(
            run_dir,
            prompt_path,
            schema_path,
            output_path,
            run_dir / "responses" / "codex_score_events.jsonl",
            stderr_path,
        )
        try:
            return ScoreResult.model_validate(data)
        except ValidationError as exc:
            raise ModelOutputError(
                f"codex score result failed schema validation: {exc}",
                stderr_path=str(stderr_path),
                response_path=str(output_path),
            ) from exc
