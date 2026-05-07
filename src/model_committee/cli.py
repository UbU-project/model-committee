import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from model_committee.config import load_config
from model_committee.consistency.report import format_consistency_report
from model_committee.constants import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_RUNS_DIR,
    EXIT_CONSISTENCY_FAILURE,
    EXIT_INVALID_MODEL_OUTPUT,
    EXIT_NO_ACCEPTABLE_SELECTION,
    EXIT_NO_VALID_PATCH_PROPOSALS,
    EXIT_PROVIDER_FAILURE,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    REQUIRED_REPO_FILES,
    VERSION,
)
from model_committee.errors import (
    ConfigError,
    ConsistencyError,
    ModelOutputError,
    PatchValidationError,
    ProviderError,
    SelectionError,
)
from model_committee.orchestration.check import run_check
from model_committee.orchestration.rank import run_rank
from model_committee.orchestration.run_loop import run_loop
from model_committee.orchestration.work_generate import run_work_generate
from model_committee.orchestration.work_score import run_work_score
from model_committee.orchestration.work_select import run_work_select
from model_committee.providers.ollama import check_ollama_reachable, list_ollama_models


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="model-committee")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common_repo(command):
        command.add_argument("--repo", required=True, type=Path)
        command.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
        command.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS_DIR)

    check = sub.add_parser("check")
    add_common_repo(check)
    rank = sub.add_parser("rank")
    add_common_repo(rank)
    work_generate = sub.add_parser("work-generate")
    add_common_repo(work_generate)
    work_generate.add_argument("--question", required=True)
    work_generate.add_argument("--fake-providers", action="store_true")
    work_score = sub.add_parser("work-score")
    work_score.add_argument("--run", required=True, type=Path)
    work_score.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    work_score.add_argument("--fake-providers", action="store_true")
    work_select = sub.add_parser("work-select")
    work_select.add_argument("--run", required=True, type=Path)
    loop = sub.add_parser("run-loop")
    add_common_repo(loop)
    loop.add_argument("--fake-providers", action="store_true")
    doctor = sub.add_parser("doctor")
    add_common_repo(doctor)
    sub.add_parser("version")
    return parser


def _doctor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    ok = True
    if sys.version_info < (3, 12):
        print("FAIL python >= 3.12 required")
        ok = False
    print("OK python")
    if shutil.which("git"):
        print("OK git")
    else:
        print("FAIL git missing")
        ok = False
    codex_path = shutil.which(config.codex.command)
    if codex_path:
        help_result = subprocess.run(
            [config.codex.command, "exec", "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        help_text = help_result.stdout
        required = [
            "--skip-git-repo-check",
            "--cd",
            "--model",
            "--sandbox",
            "--output-schema",
            "--json",
        ]
        missing = [flag for flag in required if flag not in help_text]
        if "-o" not in help_text and "--output-last-message" not in help_text:
            missing.append("-o/--output-last-message")
        if missing:
            print("FAIL codex missing flags: " + ", ".join(missing))
            ok = False
        else:
            print("OK codex")
    else:
        print("FAIL codex missing")
        ok = False
    print("WARN cannot verify Codex web search is disabled")
    reachable, _message = check_ollama_reachable(config.ollama.base_url)
    if reachable:
        print("OK ollama reachable")
        try:
            installed = set(list_ollama_models(config.ollama.base_url))
            for model in config.ollama.models:
                if model.enabled and model.name not in installed:
                    print(f"WARN ollama model not installed: {model.name}")
        except Exception as exc:
            print(f"WARN could not list Ollama models: {exc}")
    else:
        print("WARN ollama not reachable")
    for filename in REQUIRED_REPO_FILES:
        if not (args.repo / filename).exists():
            print(f"FAIL missing repo file: {filename}")
            ok = False
    args.runs_dir.mkdir(parents=True, exist_ok=True)
    test_file = args.runs_dir / ".doctor_write_test"
    try:
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        print("OK runs dir writable")
    except OSError:
        print("FAIL runs dir not writable")
        ok = False
    return EXIT_SUCCESS if ok else EXIT_RUNTIME_ERROR


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "version":
            print(f"model-committee {VERSION}")
            return EXIT_SUCCESS
        if args.command == "doctor":
            return _doctor(args)
        if args.command == "check":
            report = run_check(args.repo)
            print(format_consistency_report(report), end="")
            return EXIT_CONSISTENCY_FAILURE if report.hard_failures else EXIT_SUCCESS
        if args.command == "rank":
            ranking = run_rank(args.repo)
            print(json.dumps(ranking.model_dump(), indent=2) + "\n", end="")
            return EXIT_SUCCESS
        if args.command == "work-generate":
            config = load_config(args.config)
            run_dir = run_work_generate(
                args.repo,
                args.question,
                config,
                args.config,
                args.runs_dir,
                args.fake_providers,
                "model-committee work-generate",
            )
            print(run_dir.name)
            return EXIT_SUCCESS
        if args.command == "work-score":
            run_work_score(args.run, load_config(args.config), args.fake_providers)
            return EXIT_SUCCESS
        if args.command == "work-select":
            run_work_select(args.run)
            return EXIT_SUCCESS
        if args.command == "run-loop":
            run_dir = run_loop(
                args.repo,
                load_config(args.config),
                args.config,
                args.runs_dir,
                args.fake_providers,
            )
            print(run_dir.name)
            return EXIT_SUCCESS
    except ConsistencyError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_CONSISTENCY_FAILURE
    except ProviderError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_PROVIDER_FAILURE
    except ModelOutputError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID_MODEL_OUTPUT
    except PatchValidationError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_NO_VALID_PATCH_PROPOSALS
    except SelectionError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_NO_ACCEPTABLE_SELECTION
    except (ConfigError, OSError, ValueError, KeyError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
