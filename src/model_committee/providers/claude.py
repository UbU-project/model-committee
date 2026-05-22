import json
import re
import subprocess
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from model_committee.config import ClaudeConfig
from model_committee.errors import ModelOutputError, ProviderError
from model_committee.responses.schemas import ScoreResult, WorkProposal

T = TypeVar("T", bound=BaseModel)


class ClaudeCodeProvider:
    provider_id = "claude"

    def __init__(self, config: ClaudeConfig, repo_path: Path):
        self.config = config
        self.repo_path = repo_path

    def _run_schema_native(
        self,
        *,
        run_dir: Path,
        prompt_path: Path,
        schema_path: Path,
        output_model: type[T],
        artifact_stem: str,
    ) -> T:
        response_dir = run_dir / "responses"
        stdout_path = response_dir / f"{artifact_stem}_stdout.json"
        stderr_path = response_dir / f"{artifact_stem}_stderr.txt"
        structured_path = response_dir / f"{artifact_stem}_structured_output.json"
        metadata_path = response_dir / f"{artifact_stem}_attempt.json"
        response_dir.mkdir(parents=True, exist_ok=True)

        prompt = prompt_path.read_text(encoding="utf-8")
        schema_json = schema_path.read_text(encoding="utf-8")
        args = build_claude_argv(self.config, prompt, schema_json)
        metadata = {
            "provider_name": self.provider_id,
            "model_name": self.config.model,
            "argv": redact_claude_argv(args),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "exit_status": None,
            "timeout_seconds": self.config.timeout_seconds,
            "schema_validation": {"valid": False, "message": "not run"},
            "parsed_structured_output_path": str(structured_path),
        }

        try:
            result = subprocess.run(
                args,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.config.timeout_seconds,
                check=False,
                cwd=self.repo_path,
            )
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(exc.stdout or "", encoding="utf-8")
            stderr_path.write_text(exc.stderr or "", encoding="utf-8")
            metadata["schema_validation"] = {
                "valid": False,
                "message": f"timed out after {self.config.timeout_seconds} seconds",
            }
            _write_metadata(metadata_path, metadata)
            raise ProviderError(
                f"claude timed out after {self.config.timeout_seconds} seconds",
                timeout_seconds=self.config.timeout_seconds,
                stderr_path=str(stderr_path),
                response_path=str(stdout_path),
            ) from exc

        stdout_path.write_text(result.stdout, encoding="utf-8")
        stderr_path.write_text(result.stderr, encoding="utf-8")
        metadata["exit_status"] = result.returncode
        if result.returncode != 0:
            metadata["schema_validation"] = {
                "valid": False,
                "message": f"claude exited with {result.returncode}",
            }
            _write_metadata(metadata_path, metadata)
            raise ProviderError(
                f"claude exited with {result.returncode}",
                exit_status=result.returncode,
                timeout_seconds=self.config.timeout_seconds,
                stderr_path=str(stderr_path),
                response_path=str(stdout_path),
            )

        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            metadata["schema_validation"] = {
                "valid": False,
                "message": f"claude stdout is not valid JSON: {exc}",
            }
            _write_metadata(metadata_path, metadata)
            raise ModelOutputError(
                f"claude stdout is not valid JSON: {exc}",
                stderr_path=str(stderr_path),
                response_path=str(stdout_path),
            ) from exc

        if not isinstance(raw, dict) or "structured_output" not in raw:
            metadata["schema_validation"] = {
                "valid": False,
                "message": "claude output missing structured_output",
            }
            _write_metadata(metadata_path, metadata)
            raise ModelOutputError(
                "claude output missing structured_output",
                stderr_path=str(stderr_path),
                response_path=str(stdout_path),
            )

        structured = raw["structured_output"]
        if isinstance(structured, str):
            try:
                structured = json.loads(structured)
            except json.JSONDecodeError as exc:
                metadata["schema_validation"] = {
                    "valid": False,
                    "message": f"structured_output string is not valid JSON: {exc}",
                }
                _write_metadata(metadata_path, metadata)
                raise ModelOutputError(
                    f"claude structured_output is not valid JSON: {exc}",
                    stderr_path=str(stderr_path),
                    response_path=str(stdout_path),
                ) from exc
        structured_path.write_text(json.dumps(structured, indent=2) + "\n", encoding="utf-8")

        try:
            parsed = output_model.model_validate(structured)
        except ValidationError as exc:
            metadata["schema_validation"] = {
                "valid": False,
                "message": f"structured_output failed schema validation: {exc}",
            }
            _write_metadata(metadata_path, metadata)
            raise ModelOutputError(
                f"claude structured_output failed schema validation: {exc}",
                stderr_path=str(stderr_path),
                response_path=str(structured_path),
            ) from exc

        metadata["schema_validation"] = {"valid": True, "message": None}
        _write_metadata(metadata_path, metadata)
        return parsed

    def generate_work_proposal(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> WorkProposal:
        return self._run_schema_native(
            run_dir=run_dir,
            prompt_path=prompt_path,
            schema_path=schema_path,
            output_model=WorkProposal,
            artifact_stem="claude_work",
        )

    def score_work_proposals(
        self, run_dir: Path, prompt_path: Path, schema_path: Path
    ) -> ScoreResult:
        artifact_stem = prompt_path.stem
        return self._run_schema_native(
            run_dir=run_dir,
            prompt_path=prompt_path,
            schema_path=schema_path,
            output_model=ScoreResult,
            artifact_stem=artifact_stem,
        )


def build_claude_argv(config: ClaudeConfig, prompt: str, schema_json: str) -> list[str]:
    args = [config.command]
    if config.bare:
        args.append("--bare")
    args.extend(
        [
            "--print",
            prompt,
            "--output-format",
            "json",
            "--json-schema",
            schema_json,
            "--tools",
            config.tools,
            "--model",
            config.model,
            "--max-turns",
            str(config.max_turns),
        ]
    )
    if config.max_budget_usd is not None:
        args.extend(["--max-budget-usd", str(config.max_budget_usd)])
    return args


def redact_claude_argv(args: list[str]) -> list[str]:
    redacted = list(args)
    for flag in ("--print", "--json-schema"):
        try:
            redacted[redacted.index(flag) + 1] = f"<{flag.removeprefix('--')}>"
        except (ValueError, IndexError):
            pass
    return redacted


def parse_claude_version(text: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def claude_version_at_least(found: str, minimum: str) -> bool:
    found_parts = parse_claude_version(found)
    minimum_parts = parse_claude_version(minimum)
    if found_parts is None or minimum_parts is None:
        return False
    return found_parts >= minimum_parts


def _write_metadata(path: Path, metadata: dict) -> None:
    path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
