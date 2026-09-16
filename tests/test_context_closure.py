from pathlib import Path

import pytest

from model_committee.context import RepoContext, SectionIndex, compute_closure, find_section_refs

FIXTURE = Path("tests/fixtures/valid_repo")


def test_section_index_is_nested_inclusive():
    index = SectionIndex.from_text(
        "D.md",
        "## 2. Principles\n\nintro\n\n### 2.1 Sub\n\nsub body\n\n## 3. Next\n\nnext\n",
    )
    assert "sub body" in index.get("2").text
    assert "next" not in index.get("2").text
    assert index.get("2.1").text.startswith("### 2.1 Sub")


def test_section_index_keys_unnumbered_sections_by_slug():
    index = SectionIndex.from_text("D.md", "## Central invariants\n\nbody\n")
    assert index.get("central-invariants").title == "Central invariants"


def test_section_index_ignores_id_headings():
    index = SectionIndex.from_text("DECISIONS.md", "## UBU-D0001: A decision\n\nbody\n")
    assert index.sections == {}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("see DESIGN.md §4.1 now", {"DESIGN.md": {"4.1"}}),
        ("DESIGN.md §§15.2.2, 16", {"DESIGN.md": {"15.2.2", "16"}}),
        ("SYNC.md §4, §8, §9", {"SYNC.md": {"4", "8", "9"}}),
        (
            "DESIGN.md §17.9; SYNC.md §8, §13, Appendix A",
            {"DESIGN.md": {"17.9"}, "SYNC.md": {"8", "13"}},
        ),
    ],
)
def test_find_section_refs(text, expected):
    assert find_section_refs(text) == expected


def test_find_section_refs_ignores_unqualified_sections():
    # a bare section number is ambiguous across source files
    assert find_section_refs("as described in §15 above") == {}


def test_closure_follows_transitive_dependencies():
    context = RepoContext.load(FIXTURE)
    result = compute_closure(context, "UBU-Q0003")
    # Q0003 depends on Q0001; both must be present, and nothing unrelated
    assert result.question_ids == ["UBU-Q0001", "UBU-Q0003"]


def test_closure_includes_resolving_decisions():
    context = RepoContext.load(FIXTURE)
    result = compute_closure(context, "UBU-Q0002")
    assert "UBU-D0001" in result.decision_ids


def test_closure_is_deterministic():
    context = RepoContext.load(FIXTURE)
    first = compute_closure(context, "UBU-Q0003")
    second = compute_closure(context, "UBU-Q0003")
    assert first.model_dump() == second.model_dump()


def test_closure_reports_unresolvable_section_refs():
    context = RepoContext.load(FIXTURE)
    context.questions.entries["UBU-Q0001"].text += "\nSee DESIGN.md §99.\n"
    result = compute_closure(context, "UBU-Q0001")
    assert result.missing_refs == {"DESIGN.md": ["99"]}


def test_closure_drops_sections_contained_by_a_selected_ancestor():
    context = RepoContext.load(FIXTURE)
    context.sections["DESIGN.md"] = SectionIndex.from_text(
        "DESIGN.md", "## 3. Top\n\nintro\n\n### 3.1 Sub\n\nsub\n"
    )
    context.questions.entries["UBU-Q0001"].text += "\nSee DESIGN.md §3, §3.1.\n"
    result = compute_closure(context, "UBU-Q0001")
    # §3 already contains §3.1; emitting both would duplicate the text
    assert result.sections["DESIGN.md"] == ["3"]


def test_closure_total_chars_counts_each_section_once():
    context = RepoContext.load(FIXTURE)
    context.sections["DESIGN.md"] = SectionIndex.from_text(
        "DESIGN.md", "## 3. Top\n\nintro\n\n### 3.1 Sub\n\nsub\n"
    )
    context.questions.entries["UBU-Q0001"].text += "\nSee DESIGN.md §3, §3.1.\n"
    result = compute_closure(context, "UBU-Q0001")
    section_chars = len(context.sections["DESIGN.md"].get("3").text)
    question_chars = len(context.questions.entries["UBU-Q0001"].text)
    core_chars = sum(
        len(context.sections[name].get(key).text)
        for name, keys in result.core_sections.items()
        for key in keys
    )
    # §3.1 is inside §3; its characters must not be counted twice
    assert result.total_chars == question_chars + section_chars + core_chars


def test_check_reports_thin_context_for_unlinked_question(tmp_path):
    from model_committee.consistency.checker import check_repo

    for name in (
        "DESIGN.md",
        "DECISIONS.md",
        "PLANNING_KERNEL_CONTRACT.md",
        "DEVICE_SYNC_AND_COMPARTMENT_CONTRACT.md",
    ):
        (tmp_path / name).write_text(f"# {name}\n", encoding="utf-8")
    (tmp_path / "OPEN_QUESTIONS.md").write_text(
        "# Open Questions\n\n## UBU-Q0001: Unlinked\n\n"
        "Status: Open Priority: MVP important Phase: Phase 1 Decision type: Process "
        "Auto-choice eligibility: Auto eligible Importance score: 10 "
        "Automation-likelihood score: 10 Risk score: 10 Answerability score: 10 "
        "Depends on: None Blocks: None Resolved by: Unresolved Last scored: Never "
        "Scored from commit: None\n\n### Current direction\n\nnone\n\n---\n",
        encoding="utf-8",
    )
    report = check_repo(tmp_path)
    codes = {issue.code for issue in report.warnings}
    assert "QUESTION_CONTEXT_THIN" in codes
    # the retired whole-file budget warnings must not come back
    assert not any(code.startswith("DECISIONS_PROMPT_BUDGET") for code in codes)


def test_check_reports_unresolvable_section_reference(tmp_path):
    from model_committee.consistency.checker import check_repo

    for name in (
        "DECISIONS.md",
        "PLANNING_KERNEL_CONTRACT.md",
        "DEVICE_SYNC_AND_COMPARTMENT_CONTRACT.md",
    ):
        (tmp_path / name).write_text(f"# {name}\n", encoding="utf-8")
    (tmp_path / "DESIGN.md").write_text("# Design\n\n## 1. Real\n\nbody\n", encoding="utf-8")
    (tmp_path / "OPEN_QUESTIONS.md").write_text(
        "# Open Questions\n\n## UBU-Q0001: Bad ref\n\n"
        "Status: Open Priority: MVP important Phase: Phase 1 Decision type: Process "
        "Auto-choice eligibility: Auto eligible Importance score: 10 "
        "Automation-likelihood score: 10 Risk score: 10 Answerability score: 10 "
        "Depends on: None Blocks: None Resolved by: Unresolved Last scored: Never "
        "Scored from commit: None\n\nSee DESIGN.md §99.\n\n### Current direction\n\nx\n\n---\n",
        encoding="utf-8",
    )
    report = check_repo(tmp_path)
    issue = next(i for i in report.warnings if i.code == "QUESTION_SECTION_REF_UNRESOLVED")
    assert "DESIGN.md §99" in issue.message
    assert issue.question_id == "UBU-Q0001"
