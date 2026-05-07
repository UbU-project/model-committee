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
