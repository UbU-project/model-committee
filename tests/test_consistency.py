from model_committee.consistency.checker import check_repo


def test_valid_repo_has_no_hard_failures():
    report = check_repo("tests/fixtures/valid_repo")
    assert report.status == "passed"
    assert report.hard_failures == []


def test_invalid_fixtures_report_expected_codes():
    cases = {
        "invalid_missing_answerability_score": "MISSING_REQUIRED_METADATA",
        "invalid_priority_value": "INVALID_ENUM_VALUE",
        "invalid_missing_required_field": "MISSING_REQUIRED_METADATA",
        "invalid_nonexistent_dependency": "NONEXISTENT_DEPENDENCY",
        "invalid_dependency_cycle": "QUESTION_DEPENDENCY_CYCLE",
        "invalid_nonexistent_decision_reference": "NONEXISTENT_DECISION_REFERENCE",
        "invalid_duplicate_question_id": "DUPLICATE_QUESTION_ID",
    }
    for fixture, code in cases.items():
        report = check_repo(f"tests/fixtures/{fixture}")
        assert report.status == "failed"
        assert code in {failure.code for failure in report.hard_failures}


def test_missing_canonical_file_is_hard_consistency_failure(tmp_path):
    (tmp_path / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
    (tmp_path / "DECISIONS.md").write_text("# Decisions\n", encoding="utf-8")

    report = check_repo(tmp_path)

    assert report.status == "failed"
    assert {failure.code for failure in report.hard_failures} == {"MISSING_REPO_FILE"}
    assert "OPEN_QUESTIONS.md" in report.hard_failures[0].message


def test_solved_tombstone_does_not_need_current_direction(tmp_path):
    (tmp_path / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
    (tmp_path / "DECISIONS.md").write_text(
        "# Decisions\n\n## UBU-D0001: Existing Decision\n\nAccepted.\n",
        encoding="utf-8",
    )
    (tmp_path / "PLANNING_KERNEL_CONTRACT.md").write_text(
        "# Planning Kernel Contract\n", encoding="utf-8"
    )
    (tmp_path / "OPEN_QUESTIONS.md").write_text(
        """# Open Questions

## UBU-Q0001: Solved Question

Status: Solved Priority: MVP important Phase: Phase 1 Decision type: Process Auto-choice eligibility: Auto eligible Importance score: 80 Automation-likelihood score: 70 Risk score: 20 Answerability score: 100 Depends on: None Blocks: None Resolved by: UBU-D0001 Last scored: 2026-05-26 Scored from commit: None
Resolved. See UBU-D0001.

---
""",
        encoding="utf-8",
    )

    report = check_repo(tmp_path)

    assert report.status == "passed"
    assert "QUESTION_HAS_NO_CURRENT_DIRECTION" not in {warning.code for warning in report.warnings}
