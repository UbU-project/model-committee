import re

from model_committee.constants import DECISIONS_FILE, OPEN_QUESTIONS_FILE
from model_committee.context.closure import ClosureResult, RepoContext

QUESTION_ID_RE = re.compile(r"^UBU-Q([0-9]{4})$")
DECISION_ID_RE = re.compile(r"^UBU-D([0-9]{4})$")


def next_free_ids(context: RepoContext) -> tuple[str, str]:
    """Lowest unused question and decision ids.

    Models allocate ids for questions and decisions they add. They no longer see whole
    files, so the next free id has to be supplied or they will collide with existing
    entries.
    """

    def _next(ids, pattern, prefix):
        numbers = [int(m.group(1)) for i in ids if (m := pattern.match(i))]
        return f"{prefix}{(max(numbers) + 1 if numbers else 1):04d}"

    return (
        _next(context.questions.entries, QUESTION_ID_RE, "UBU-Q"),
        _next(context.decisions.entries, DECISION_ID_RE, "UBU-D"),
    )


def render_excerpts(
    context: RepoContext,
    closure: ClosureResult,
    exclude_question_id: str | None = None,
) -> str:
    """Render the closure as labelled markdown excerpts.

    Every excerpt is labelled with the file and the id or section it came from, so a
    proposal can cite its source and a reviewer can check what the model was shown.
    """
    parts: list[str] = []

    questions = [q for q in closure.question_ids if q != exclude_question_id]
    if questions:
        parts.append(f"### {OPEN_QUESTIONS_FILE} — related questions\n")
        for qid in questions:
            entry = context.questions.entries[qid]
            parts.append(f"#### {qid}\n\n```markdown\n{entry.text.strip()}\n```\n")

    if closure.decision_ids:
        parts.append(f"### {DECISIONS_FILE} — cited decisions\n")
        for did in closure.decision_ids:
            entry = context.decisions.entries[did]
            parts.append(f"#### {did}\n\n```markdown\n{entry.text.strip()}\n```\n")

    merged: dict[str, list[str]] = {}
    for group in (closure.sections, closure.core_sections):
        for filename, keys in group.items():
            merged.setdefault(filename, []).extend(keys)

    for filename in sorted(merged):
        index = context.sections[filename]
        parts.append(f"### {filename} — referenced sections\n")
        for key in merged[filename]:
            section = index.get(key)
            if section is None:
                continue
            parts.append(
                f"#### {filename} §{key} — {section.title}\n\n"
                f"```markdown\n{section.text.strip()}\n```\n"
            )

    return "\n".join(parts).strip()
