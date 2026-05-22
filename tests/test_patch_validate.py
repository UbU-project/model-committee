import json
import subprocess

from model_committee.orchestration.work_select import run_work_select
from model_committee.patches.extract import enforce_allowed_patch_files
from model_committee.patches.validate import RECOUNT_NORMALIZATION_WARNING, validate_patch
from model_committee.runs.manifest import RunManifest, RunStatus, write_manifest


VALID_PATCH = """diff --git a/DESIGN.md b/DESIGN.md
index d2a4c9f..19eb29d 100644
--- a/DESIGN.md
+++ b/DESIGN.md
@@ -1,4 +1,4 @@
 # Design
 
-Original design line.
+Selected design line.

"""

CORRUPT_HUNK_COUNT_PATCH = """diff --git a/DESIGN.md b/DESIGN.md
index d2a4c9f..19eb29d 100644
--- a/DESIGN.md
+++ b/DESIGN.md
@@ -1,99 +1,99 @@
 # Design
 
-Original design line.
+Selected design line.
 
"""

BAD_CONTEXT_PATCH = """diff --git a/DESIGN.md b/DESIGN.md
index d2a4c9f..19eb29d 100644
--- a/DESIGN.md
+++ b/DESIGN.md
@@ -1,4 +1,4 @@
 # Design
 
-Missing design line.
+Selected design line.
 
"""


def test_patch_allowlist():
    assert enforce_allowed_patch_files(VALID_PATCH) == ["DESIGN.md"]


def test_patch_validation_applies(git_fixture_repo):
    result = validate_patch(git_fixture_repo, "proposal", VALID_PATCH)
    assert result.patch_applies is True
    assert result.allowlist_passed is True
    assert result.normalized_patch is None


def test_patch_validation_rejects_forbidden_file(git_fixture_repo):
    patch = "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n"
    result = validate_patch(git_fixture_repo, "proposal", patch)
    assert result.allowlist_passed is False
    assert result.patch_applies is False
    assert result.ordinary_error is None
    assert result.recount_error is None
    assert result.normalized_patch is None


def test_corrupt_hunk_count_patch_fails_ordinary_but_passes_recount(git_fixture_repo, tmp_path):
    patch_path = tmp_path / "corrupt.patch"
    patch_path.write_text(CORRUPT_HUNK_COUNT_PATCH, encoding="utf-8")

    ordinary = subprocess.run(
        ["git", "-C", str(git_fixture_repo), "apply", "--check", str(patch_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    recount = subprocess.run(
        [
            "git",
            "-C",
            str(git_fixture_repo),
            "apply",
            "--check",
            "--recount",
            str(patch_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert ordinary.returncode != 0
    assert recount.returncode == 0


def test_patch_validation_normalizes_recount_patch(git_fixture_repo, tmp_path):
    result = validate_patch(git_fixture_repo, "proposal", CORRUPT_HUNK_COUNT_PATCH)

    assert result.patch_applies is True
    assert result.allowlist_passed is True
    assert result.normalized_patch is not None
    assert result.changed_files == ["DESIGN.md"]
    assert result.warnings == [RECOUNT_NORMALIZATION_WARNING]
    assert result.ordinary_error is not None
    assert "@@ -1,4 +1,4 @@" in result.normalized_patch

    normalized_path = tmp_path / "normalized.patch"
    normalized_path.write_text(result.normalized_patch, encoding="utf-8")
    normalized_check = subprocess.run(
        ["git", "-C", str(git_fixture_repo), "apply", "--check", str(normalized_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert normalized_check.returncode == 0


def test_patch_validation_invalid_when_ordinary_and_recount_fail(git_fixture_repo):
    result = validate_patch(git_fixture_repo, "proposal", BAD_CONTEXT_PATCH)

    assert result.patch_applies is False
    assert result.allowlist_passed is True
    assert result.normalized_patch is None
    assert result.ordinary_error is not None
    assert result.recount_error is not None
    assert result.error is not None
    assert "ordinary git apply --check failed" in result.error
    assert "git apply --check --recount failed" in result.error


def test_work_select_uses_normalized_patch(git_fixture_repo, tmp_path):
    validation = validate_patch(git_fixture_repo, "proposal", CORRUPT_HUNK_COUNT_PATCH)
    assert validation.normalized_patch is not None
    run_dir = tmp_path / "run"
    (run_dir / "parsed").mkdir(parents=True)
    (run_dir / "patches").mkdir()

    write_manifest(
        run_dir,
        RunManifest(
            run_id="run",
            created_at_utc="2026-05-07T00:00:00Z",
            repo_path=str(git_fixture_repo),
            base_commit="fixture",
            selected_question_id="UBU-Q0001",
            phase="work-select",
            status=RunStatus.SCORED,
        ),
    )
    proposal = {
        "proposal_id": "proposal",
        "provider_id": "codex",
        "model_name": "codex:gpt-5.5",
        "question_id": "UBU-Q0001",
        "base_commit": "fixture",
        "summary": "Update the example design line.",
        "rationale": "A minimal auditable change for the fixture question.",
        "changed_files": ["DESIGN.md"],
        "patch": CORRUPT_HUNK_COUNT_PATCH,
        "commit_message": "Update example design line",
        "validation_notes": [],
        "new_questions_added": [],
        "questions_resolved": [],
        "decisions_added": [],
        "requires_human_review": False,
    }
    score = {
        "scores": [
            {
                "proposal_id": "proposal",
                "score": 100,
                "patch_applies": True,
                "implements_selected_work": True,
                "preserves_question_schema": True,
                "avoids_unnecessary_scope": True,
                "decomposition_quality": "not_applicable",
                "risks": [],
                "required_fixes": [],
                "rationale": "Valid.",
            }
        ],
        "selected_proposal_id": "proposal",
        "selection_rationale": "Only valid proposal.",
    }
    (run_dir / "parsed" / "codex_work_proposal.json").write_text(
        json.dumps(proposal, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "parsed" / "patch_validation_results.json").write_text(
        json.dumps([validation.model_dump()], indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "parsed" / "score_result.json").write_text(
        json.dumps(score, indent=2) + "\n", encoding="utf-8"
    )
    score_matrix = [
        {
            "proposal_id": "proposal",
            "author_provider": "codex",
            "scorer_provider": "claude",
            "score": 100,
            "valid": True,
            "rationale": "Valid.",
            "required_fixes": [],
            "risks": [],
            "schema_validation": {"valid": True},
        }
    ]
    (run_dir / "parsed" / "score_matrix.json").write_text(
        json.dumps(score_matrix, indent=2) + "\n", encoding="utf-8"
    )

    run_work_select(run_dir)

    selected_patch = (run_dir / "patches" / "selected.patch").read_text(encoding="utf-8")
    assert selected_patch == validation.normalized_patch
    assert selected_patch != CORRUPT_HUNK_COUNT_PATCH
