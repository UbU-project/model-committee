from collections import Counter
from pathlib import Path

from model_committee.consistency.code_fences import code_fence_warnings
from model_committee.consistency.decision_refs import nonexistent_decision_refs
from model_committee.consistency.question_graph import dependency_edges, find_dependency_cycles
from model_committee.context.closure import RepoContext, compute_closure
from model_committee.constants import (
    PROMPT_FIXED_OVERHEAD_CHARS,
    PROMPT_SIZE_WARNING_LIMIT,
    REQUIRED_REPO_FILES,
)
from model_committee.errors import ParseError
from model_committee.markdown.decisions_parser import parse_decisions_text
from model_committee.markdown.questions_parser import parse_questions_text
from model_committee.responses.schemas import ConsistencyIssue, ConsistencyReport


def check_repo(repo: Path) -> ConsistencyReport:
    repo = Path(repo)
    hard: list[ConsistencyIssue] = []
    warnings: list[ConsistencyIssue] = []
    missing_files = [
        filename for filename in REQUIRED_REPO_FILES if not (repo / filename).is_file()
    ]
    if missing_files:
        return ConsistencyReport(
            status="failed",
            hard_failures=[
                ConsistencyIssue(
                    code="MISSING_REPO_FILE",
                    message=f"Missing canonical repo file: {filename}",
                )
                for filename in missing_files
            ],
            warnings=[],
            question_count=0,
            decision_count=0,
            dependency_edges=[],
        )

    try:
        (repo / "DESIGN.md").read_text(encoding="utf-8")
        decisions_text = (repo / "DECISIONS.md").read_text(encoding="utf-8")
        questions_text = (repo / "OPEN_QUESTIONS.md").read_text(encoding="utf-8")
        questions = parse_questions_text(questions_text)
        decisions = parse_decisions_text(decisions_text)
    except ParseError as exc:
        text = str(exc)
        code = (
            "MISSING_REQUIRED_METADATA"
            if "Missing required field" in text
            else "INVALID_ENUM_VALUE"
        )
        return ConsistencyReport(
            status="failed",
            hard_failures=[ConsistencyIssue(code=code, message=text)],
            warnings=[],
            question_count=0,
            decision_count=0,
            dependency_edges=[],
        )
    except OSError as exc:
        return ConsistencyReport(
            status="failed",
            hard_failures=[
                ConsistencyIssue(
                    code="CANNOT_READ_REPO_FILE",
                    message=f"Could not read canonical repo file: {exc}",
                )
            ],
            warnings=[],
            question_count=0,
            decision_count=0,
            dependency_edges=[],
        )

    question_counts = Counter(question.question_id for question in questions)
    for question_id, count in question_counts.items():
        if count > 1:
            hard.append(
                ConsistencyIssue(
                    code="DUPLICATE_QUESTION_ID",
                    message=f"Duplicate question ID: {question_id}",
                    question_id=question_id,
                )
            )

    decision_counts = Counter(decision.decision_id for decision in decisions)
    for decision_id, count in decision_counts.items():
        if count > 1:
            hard.append(
                ConsistencyIssue(
                    code="DUPLICATE_DECISION_ID",
                    message=f"Duplicate decision ID: {decision_id}",
                    decision_id=decision_id,
                )
            )

    question_ids = set(question_counts)
    for question in questions:
        if (
            question.metadata.importance_score is None
            or question.metadata.automation_likelihood_score is None
            or question.metadata.risk_score is None
            or question.metadata.answerability_score is None
        ):
            warnings.append(
                ConsistencyIssue(
                    code="QUESTION_SCORE_TBD",
                    message=f"{question.question_id} has TBD scores.",
                    question_id=question.question_id,
                )
            )
        if question.metadata.status == "Open" and not question.has_current_direction:
            warnings.append(
                ConsistencyIssue(
                    code="QUESTION_HAS_NO_CURRENT_DIRECTION",
                    message=f"{question.question_id} has no Current direction.",
                    question_id=question.question_id,
                )
            )
        for dependency in question.metadata.depends_on:
            if dependency not in question_ids:
                hard.append(
                    ConsistencyIssue(
                        code="NONEXISTENT_DEPENDENCY",
                        message=f"{question.question_id} depends on nonexistent {dependency}",
                        question_id=question.question_id,
                    )
                )

    for cycle in find_dependency_cycles(questions):
        hard.append(
            ConsistencyIssue(
                code="QUESTION_DEPENDENCY_CYCLE",
                message="Question dependency cycle: " + " -> ".join(cycle),
                question_id=cycle[0],
            )
        )

    for question_id, decision_id in nonexistent_decision_refs(questions, decisions):
        hard.append(
            ConsistencyIssue(
                code="NONEXISTENT_DECISION_REFERENCE",
                message=f"{question_id} resolved by nonexistent {decision_id}",
                question_id=question_id,
                decision_id=decision_id,
            )
        )

    warnings.extend(code_fence_warnings("DECISIONS.md", decisions_text))
    warnings.extend(code_fence_warnings("OPEN_QUESTIONS.md", questions_text))
    warnings.extend(_context_warnings(repo, questions))

    return ConsistencyReport(
        status="failed" if hard else "passed",
        hard_failures=hard,
        warnings=warnings,
        question_count=len(questions),
        decision_count=len(decisions),
        dependency_edges=dependency_edges(questions),
    )


def _context_warnings(repo: Path, questions: list) -> list[ConsistencyIssue]:
    """Warn about the context each open question would be given.

    Prompt size is driven by a question's dependency closure, not by whole-file size, so
    these replace the old `DECISIONS_PROMPT_BUDGET_*` warnings. They also make a missing
    reference edge visible: without them, a question with no links silently gets thin
    context and the model answers with less than it needed.
    """
    try:
        context = RepoContext.load(repo)
    except OSError:
        return []

    issues: list[ConsistencyIssue] = []
    for question in questions:
        if question.metadata.status != "Open":
            continue
        closure = compute_closure(context, question.question_id)

        budget = closure.total_chars + PROMPT_FIXED_OVERHEAD_CHARS
        if budget > PROMPT_SIZE_WARNING_LIMIT:
            issues.append(
                ConsistencyIssue(
                    code="QUESTION_CONTEXT_OVER_BUDGET",
                    message=(
                        f"{question.question_id} selects about {budget} prompt chars, "
                        f"exceeding the {PROMPT_SIZE_WARNING_LIMIT} char limit."
                    ),
                    question_id=question.question_id,
                )
            )

        for filename, keys in sorted(closure.missing_refs.items()):
            issues.append(
                ConsistencyIssue(
                    code="QUESTION_SECTION_REF_UNRESOLVED",
                    message=(
                        f"{question.question_id} references {filename} "
                        f"§{', §'.join(keys)}, which does not exist."
                    ),
                    question_id=question.question_id,
                )
            )

        if not question.metadata.depends_on and not closure.decision_ids and not closure.sections:
            issues.append(
                ConsistencyIssue(
                    code="QUESTION_CONTEXT_THIN",
                    message=(
                        f"{question.question_id} links to no question, decision, or "
                        "section, so it will be answered with almost no context."
                    ),
                    question_id=question.question_id,
                )
            )
    return issues
