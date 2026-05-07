from model_committee.markdown.metadata_parser import parse_metadata_line


def test_metadata_label_boundary_parser():
    parsed = parse_metadata_line(
        "Status: Open Priority: MVP important Phase: Phase 1 Decision type: Process "
        "Auto-choice eligibility: Auto eligible Importance score: TBD "
        "Automation-likelihood score: 10 Risk score: 20 Answerability score: TBD "
        "Depends on: UBU-Q0001, UBU-Q0002 Blocks: None Resolved by: Unresolved "
        "Last scored: Never Scored from commit: None"
    )
    assert parsed.errors == []
    assert parsed.values["Depends on"] == "UBU-Q0001, UBU-Q0002"
